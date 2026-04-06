"""
Painel Admin — Uso interno (não aparece na sidebar do cliente).

Acesso: localhost:8501/admin_revisao
Auth:   senha definida em ADMIN_PASSWORD no .env

Abas:
  1. Revisão de Produtos  — classifica produtos sem categoria / revisao_necessaria
  2. Marcas & Fabricantes — cadastra marcas e fabricantes no banco
"""

import json
import os
from datetime import datetime, timezone, timedelta

import streamlit as st

from app.utils.db import get_session, run_migrations

run_migrations()
from app.models.produto import Produto
from app.models.tenant import Tenant
from app.models.categoria import Departamento, Grupo, Categoria
from app.models.fabricante import Fabricante
from app.models.marca import Marca
from app.models.arquivo_importado import ArquivoImportado
from app.models.efd_raw import EfdRaw
from app.services.produto_padronizacao import processar_descricao
from app.services.produto_padronizacao.categorizador import invalidar_cache
from app.services.produto_padronizacao.identificador import invalidar_cache_marcas
from app.services.tenant_service import TenantService
from app.utils.formatters import formatar_cnpj, limpar_cnpj
from app.parser.renomeador import processar_renomeacao
from app.parser.bronze import BronzeProcessor
from app.parser.silver import SilverProcessor

# Oculta sidebar do cliente — esta página é de uso interno
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none; }
        [data-testid="stSidebar"]    { display: none; }
        [data-testid="collapsedControl"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# ── Auth admin ────────────────────────────────────────────────────────────────

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    st.title("Painel Admin")
    st.caption("Acesso restrito")
    with st.form("admin_login"):
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if senha == ADMIN_PASSWORD:
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.error("Senha incorreta")
    st.stop()

# ── Layout ────────────────────────────────────────────────────────────────────

st.title("Painel Admin")

aba_revisao, aba_batch, aba_marcas, aba_tokens, aba_clientes = st.tabs([
    "Revisão Individual", "Revisão em Lote", "Marcas & Fabricantes", "Tokens Desconhecidos", "Clientes & Upload",
])

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 1 — Revisão de Produtos
# ═══════════════════════════════════════════════════════════════════════════════

with aba_revisao:

    # ── Helpers ───────────────────────────────────────────────────────────────

    @st.cache_data(ttl=60)
    def _stats():
        db = next(get_session())
        try:
            total   = db.query(Produto).count()
            sem_cat = db.query(Produto).filter(Produto.categoria_id.is_(None)).count()
            revisao = db.query(Produto).filter(Produto.revisao_necessaria == True).count()
            com_cat = total - sem_cat
            return {"total": total, "sem_cat": sem_cat, "revisao": revisao, "com_cat": com_cat}
        finally:
            db.close()


    # Origens que indicam revisão humana concluída — nunca reaparecem na fila
    _ORIGENS_REVISADAS = ("manual", "manual_sem_cat")

    def _pendentes(db, filtro_tenant, apenas_sem_categoria, apenas_revisao,
                   filtro_dep_id=None, filtro_grp_id=None, limit=200):
        q = (
            db.query(Produto, Tenant)
            .join(Tenant, Produto.tenant_id == Tenant.id)
            # Exclui produtos que já passaram por revisão manual
            .filter(Produto.origem_padronizacao.notin_(_ORIGENS_REVISADAS)
                    | Produto.origem_padronizacao.is_(None))
        )
        if apenas_sem_categoria:
            q = q.filter(Produto.categoria_id.is_(None))
        elif apenas_revisao:
            q = q.filter(Produto.revisao_necessaria == True)
        else:
            q = q.filter(
                (Produto.categoria_id.is_(None)) | (Produto.revisao_necessaria == True)
            )
        if filtro_tenant:
            q = q.filter(Tenant.nome == filtro_tenant)
        if filtro_dep_id:
            q = q.filter(Produto.departamento_id == filtro_dep_id)
        if filtro_grp_id:
            q = q.filter(Produto.grupo_id == filtro_grp_id)
        return q.order_by(Produto.tenant_id, Produto.descr_item).limit(limit).all()


    def _salvar_classificacao(db, produto_id: int, cat_id, grp_id, dep_id, descarta: bool):
        produto = db.query(Produto).filter(Produto.id == produto_id).first()
        if not produto:
            return
        if descarta:
            produto.revisao_necessaria  = False
            produto.origem_padronizacao = "manual_sem_cat"
        else:
            produto.categoria_id        = cat_id
            produto.grupo_id            = grp_id
            produto.departamento_id     = dep_id
            produto.score_categoria     = 1.0
            produto.revisao_necessaria  = False
            produto.origem_padronizacao = "manual"
        db.commit()
        invalidar_cache()

    # ── Stats ─────────────────────────────────────────────────────────────────

    stats = _stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de produtos", stats["total"])
    c2.metric("Com categoria",     stats["com_cat"])
    c3.metric("Sem categoria",     stats["sem_cat"])
    c4.metric("Revisão necessária", stats["revisao"])

    st.divider()

    # ── Filtros ───────────────────────────────────────────────────────────────

    db = next(get_session())
    try:
        tenants      = [t.nome for t in db.query(Tenant).order_by(Tenant.nome).all()]
        departamentos = db.query(Departamento).order_by(Departamento.descricao).all()
    except Exception:
        db.close()
        raise

    col_f1, col_f2 = st.columns([2, 3])
    with col_f1:
        filtro_tenant = st.selectbox("Cliente", ["Todos"] + tenants, key="filtro_tenant")
    with col_f2:
        modo = st.radio(
            "Filtrar por",
            ["Sem categoria + revisão", "Sem categoria", "Revisão necessária"],
            horizontal=True,
        )

    # Filtro por departamento / grupo (sugestão do pipeline)
    col_f3, col_f4 = st.columns(2)
    dep_nomes_filtro = ["Todos os departamentos"] + [d.descricao for d in departamentos]
    with col_f3:
        filtro_dep_nome = st.selectbox("Departamento (sugestão pipeline)", dep_nomes_filtro, key="filtro_dep")

    filtro_dep_id = None
    filtro_grp_id = None
    if filtro_dep_nome != "Todos os departamentos":
        dep_obj_filtro = next((d for d in departamentos if d.descricao == filtro_dep_nome), None)
        if dep_obj_filtro:
            filtro_dep_id = dep_obj_filtro.id
            grupos_filtro = (
                db.query(Grupo)
                .filter(Grupo.departamento_id == filtro_dep_id)
                .order_by(Grupo.descricao)
                .all()
            )
            grp_nomes_filtro = ["Todos os grupos"] + [g.descricao for g in grupos_filtro]
            with col_f4:
                filtro_grp_nome = st.selectbox("Grupo", grp_nomes_filtro, key="filtro_grp")
            if filtro_grp_nome != "Todos os grupos":
                grp_obj_filtro = next((g for g in grupos_filtro if g.descricao == filtro_grp_nome), None)
                if grp_obj_filtro:
                    filtro_grp_id = grp_obj_filtro.id
    else:
        with col_f4:
            st.selectbox("Grupo", ["— selecione um departamento primeiro —"],
                         disabled=True, key="filtro_grp")

    apenas_sem_cat = (modo == "Sem categoria")
    apenas_revisao = (modo == "Revisão necessária")
    filtro_t       = None if filtro_tenant == "Todos" else filtro_tenant

    # Resetar índice ao trocar filtros
    filtro_key = (filtro_t, modo, filtro_dep_id, filtro_grp_id)
    if st.session_state.get("_ultimo_filtro") != filtro_key:
        st.session_state.rev_idx = 0
        st.session_state["_ultimo_filtro"] = filtro_key

    pendentes = _pendentes(db, filtro_t, apenas_sem_cat, apenas_revisao,
                           filtro_dep_id, filtro_grp_id)

    if not pendentes:
        st.success("Nenhum produto pendente de revisão com os filtros selecionados.")
        db.close()
        st.stop()

    st.caption(f"{len(pendentes)} produtos pendentes (limite 200 por consulta)")
    st.divider()

    # ── Revisão um a um ───────────────────────────────────────────────────────

    if "rev_idx" not in st.session_state:
        st.session_state.rev_idx = 0

    if st.session_state.rev_idx >= len(pendentes):
        st.session_state.rev_idx = 0

    produto, tenant = pendentes[st.session_state.rev_idx]

    progresso = st.session_state.rev_idx / len(pendentes)
    st.progress(progresso, text=f"Produto {st.session_state.rev_idx + 1} de {len(pendentes)}")

    col_info, col_form = st.columns([2, 3])

    with col_info:
        st.subheader("Produto")
        st.markdown(f"**Cliente:** {tenant.nome}")
        st.markdown(f"**Código:** `{produto.cod_item}`")
        st.markdown("**Descrição original:**")
        st.code(produto.descr_item, language=None)

        try:
            resultado = processar_descricao(produto.descr_item, session=db)
            st.markdown("**Descrição padronizada:**")
            st.code(resultado.descricao_padrao, language=None)
            col_a, col_b = st.columns(2)
            col_a.markdown(f"**Marca:** {resultado.marca or '—'}")
            col_a.markdown(f"**Fabricante:** {resultado.fabricante or '—'}")
            col_b.markdown(f"**Embalagem:** {resultado.tipo_embalagem or '—'}")
            col_b.markdown(f"**Qtd/Unid:** {resultado.peso_volume_valor or ''} {resultado.peso_volume_unidade or '—'}")
            if resultado.grupo_nome:
                st.info(f"Pipeline sugeriu: **{resultado.departamento_nome}** → **{resultado.grupo_nome}**  (score: {resultado.score_categoria:.0%})")
        except Exception:
            pass

    with col_form:
        st.subheader("Classificação")

        dep_opcoes = {d.descricao: d for d in departamentos}
        dep_nomes  = ["— selecione —"] + sorted(dep_opcoes.keys())

        dep_sugerido = getattr(resultado, "departamento_nome", None) if "resultado" in dir() else None
        dep_idx = dep_nomes.index(dep_sugerido) if dep_sugerido and dep_sugerido in dep_nomes else 0

        dep_sel = st.selectbox("Departamento", dep_nomes, index=dep_idx, key=f"dep_{produto.id}")

        grp_sel_id  = None
        grp_sel_obj = None
        cat_sel_id  = None

        if dep_sel != "— selecione —":
            dep_obj = dep_opcoes[dep_sel]
            grupos  = (
                db.query(Grupo)
                .filter(Grupo.departamento_id == dep_obj.id)
                .order_by(Grupo.descricao)
                .all()
            )
            grp_opcoes = {g.descricao: g for g in grupos}
            grp_nomes  = ["— selecione —"] + list(grp_opcoes.keys())

            grp_sugerido = getattr(resultado, "grupo_nome", None) if "resultado" in dir() else None
            grp_idx = grp_nomes.index(grp_sugerido) if grp_sugerido and grp_sugerido in grp_nomes else 0

            grp_sel = st.selectbox("Grupo", grp_nomes, index=grp_idx, key=f"grp_{produto.id}")

            if grp_sel != "— selecione —":
                grp_sel_obj = grp_opcoes[grp_sel]
                categorias  = (
                    db.query(Categoria)
                    .filter(Categoria.grupo_id == grp_sel_obj.id)
                    .order_by(Categoria.descricao)
                    .all()
                )
                cat_opcoes = {c.descricao: c for c in categorias}
                cat_nomes  = ["— selecione —"] + list(cat_opcoes.keys())

                cat_sel = st.selectbox("Categoria", cat_nomes, key=f"cat_{produto.id}")
                if cat_sel != "— selecione —":
                    cat_sel_id = cat_opcoes[cat_sel].id

        st.write("")

        col_b1, col_b2, col_b3, col_b4 = st.columns(4)

        with col_b1:
            if st.button("Aprovar", type="primary", use_container_width=True,
                         disabled=(grp_sel_obj is None)):
                _salvar_classificacao(
                    db, produto.id,
                    cat_id=cat_sel_id,
                    grp_id=grp_sel_obj.id if grp_sel_obj else None,
                    dep_id=dep_opcoes[dep_sel].id if dep_sel != "— selecione —" else None,
                    descarta=False,
                )
                _stats.clear()
                st.session_state.rev_idx += 1
                db.close()
                st.rerun()

        with col_b2:
            if st.button("Pular", use_container_width=True):
                st.session_state.rev_idx += 1
                db.close()
                st.rerun()

        with col_b3:
            if st.button("Sem categoria", use_container_width=True,
                         help="Marca como revisado mas sem categoria"):
                _salvar_classificacao(db, produto.id, None, None, None, descarta=True)
                _stats.clear()
                st.session_state.rev_idx += 1
                db.close()
                st.rerun()

        with col_b4:
            if st.button("Sair", use_container_width=True):
                db.close()
                st.session_state.admin_auth = False
                st.rerun()

    # ── Tabela de pendentes ───────────────────────────────────────────────────

    st.divider()
    with st.expander(f"Ver todos os {len(pendentes)} pendentes"):
        import pandas as pd
        rows = []
        for p, t in pendentes:
            rows.append({
                "Cliente":     t.nome,
                "Código":      p.cod_item,
                "Descrição":   p.descr_item,
                "Padronizada": p.descricao_padrao or "",
                "Score pad.":  float(p.score_padronizacao or 0),
                "Score cat.":  float(p.score_categoria or 0),
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score pad.": st.column_config.ProgressColumn(format="%.0%", min_value=0, max_value=1),
                "Score cat.": st.column_config.ProgressColumn(format="%.0%", min_value=0, max_value=1),
            }
        )

    db.close()

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 2 — Revisão em Lote
# ═══════════════════════════════════════════════════════════════════════════════

with aba_batch:
    import pandas as pd

    st.markdown(
        "Agrupa produtos pela **sugestão do pipeline** (departamento → grupo). "
        "Selecione os produtos corretos e aprove todos de uma vez."
    )

    db_batch = next(get_session())
    try:
        # ── Filtros ──────────────────────────────────────────────────────────
        tenants_batch = [t.nome for t in db_batch.query(Tenant).order_by(Tenant.nome).all()]
        deps_batch = db_batch.query(Departamento).order_by(Departamento.descricao).all()

        col_bf1, col_bf2 = st.columns(2)
        with col_bf1:
            filtro_tenant_batch = st.selectbox(
                "Cliente", ["Todos"] + tenants_batch, key="batch_tenant",
            )
        with col_bf2:
            modo_batch = st.radio(
                "Mostrar",
                ["Com sugestão do pipeline", "Todos sem categoria"],
                horizontal=True, key="batch_modo",
            )

        col_bf3, col_bf4 = st.columns(2)
        dep_nomes_batch = ["Todos os departamentos"] + [d.descricao for d in deps_batch]
        with col_bf3:
            filtro_dep_batch = st.selectbox("Departamento", dep_nomes_batch, key="batch_dep")

        filtro_dep_id_batch = None
        filtro_grp_id_batch = None
        if filtro_dep_batch != "Todos os departamentos":
            dep_obj_batch = next((d for d in deps_batch if d.descricao == filtro_dep_batch), None)
            if dep_obj_batch:
                filtro_dep_id_batch = dep_obj_batch.id
                grupos_batch_filtro = (
                    db_batch.query(Grupo)
                    .filter(Grupo.departamento_id == filtro_dep_id_batch)
                    .order_by(Grupo.descricao).all()
                )
                grp_nomes_batch = ["Todos os grupos"] + [g.descricao for g in grupos_batch_filtro]
                with col_bf4:
                    filtro_grp_batch = st.selectbox("Grupo", grp_nomes_batch, key="batch_grp")
                if filtro_grp_batch != "Todos os grupos":
                    grp_obj_batch = next((g for g in grupos_batch_filtro if g.descricao == filtro_grp_batch), None)
                    if grp_obj_batch:
                        filtro_grp_id_batch = grp_obj_batch.id
        else:
            with col_bf4:
                st.selectbox("Grupo", ["— selecione um departamento primeiro —"],
                             disabled=True, key="batch_grp")

        # ── Query: produtos pendentes com sugestão do pipeline ───────────────
        q_batch = (
            db_batch.query(Produto, Tenant)
            .join(Tenant, Produto.tenant_id == Tenant.id)
            .filter(
                Produto.origem_padronizacao.notin_(_ORIGENS_REVISADAS)
                | Produto.origem_padronizacao.is_(None)
            )
            .filter(Produto.categoria_id.is_(None))
        )
        if filtro_tenant_batch != "Todos":
            q_batch = q_batch.filter(Tenant.nome == filtro_tenant_batch)
        if modo_batch == "Com sugestão do pipeline":
            q_batch = q_batch.filter(Produto.grupo_id.isnot(None))
        if filtro_dep_id_batch:
            q_batch = q_batch.filter(Produto.departamento_id == filtro_dep_id_batch)
        if filtro_grp_id_batch:
            q_batch = q_batch.filter(Produto.grupo_id == filtro_grp_id_batch)

        pendentes_batch = q_batch.order_by(
            Produto.departamento_id, Produto.grupo_id, Produto.descr_item,
        ).limit(500).all()

        if not pendentes_batch:
            st.success("Nenhum produto pendente para revisão em lote.")
        else:
            # ── Agrupar por Departamento → Grupo ─────────────────────────────
            from collections import defaultdict

            # Re-processar cada produto pelo pipeline para ter a sugestão atualizada
            from app.services.produto_padronizacao.categorizador import carregar_indice
            from app.services.produto_padronizacao.identificador import carregar_marcas_do_banco
            carregar_indice(db_batch)
            carregar_marcas_do_banco(db_batch)

            grupos_agrupados = defaultdict(list)
            for produto, tenant in pendentes_batch:
                resultado = processar_descricao(produto.descr_item, session=db_batch)
                chave = None
                if resultado.grupo_nome:
                    chave = f"{resultado.departamento_nome} → {resultado.grupo_nome}"
                elif modo_batch == "Todos sem categoria":
                    chave = "Sem sugestão"
                if chave:
                    grupos_agrupados[chave].append({
                        "produto": produto,
                        "tenant": tenant,
                        "resultado": resultado,
                    })

            st.caption(f"{len(pendentes_batch)} produtos em {len(grupos_agrupados)} grupos")
            st.divider()

            # ── Renderizar cada grupo ────────────────────────────────────────
            for grupo_label, items in sorted(
                grupos_agrupados.items(), key=lambda x: -len(x[1])
            ):
                with st.expander(f"**{grupo_label}** — {len(items)} produtos"):
                    # Montar dataframe
                    rows_batch = []
                    for item in items:
                        p = item["produto"]
                        r = item["resultado"]
                        rows_batch.append({
                            "✔":            True,
                            "id":           p.id,
                            "Cliente":      item["tenant"].nome,
                            "Código":       p.cod_item,
                            "Descrição":    p.descr_item,
                            "Padronizada":  r.descricao_padrao,
                            "Marca":        r.marca or "—",
                            "Cat. sugerida": r.categoria_nome or "—",
                            "Score":        r.score_categoria,
                        })

                    df_batch = pd.DataFrame(rows_batch)

                    # Checkbox por linha + id oculto
                    edited = st.data_editor(
                        df_batch,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        disabled=["Cliente", "Código", "Descrição", "Padronizada",
                                  "Marca", "Cat. sugerida", "Score"],
                        column_config={
                            "✔": st.column_config.CheckboxColumn(
                                "✔",
                                help="Desmarque para excluir este produto do lote",
                                default=True,
                                width="small",
                            ),
                            "id": None,   # oculta coluna id
                            "Score": st.column_config.ProgressColumn(
                                format="%.0%", min_value=0, max_value=1,
                            ),
                        },
                        key=f"batch_df_{grupo_label}",
                    )

                    # IDs selecionados (checkbox marcado)
                    selected_ids = edited[edited["✔"] == True]["id"].tolist()
                    n_sel = len(selected_ids)
                    if n_sel < len(items):
                        st.caption(f"ℹ️ {n_sel} de {len(items)} produtos selecionados")

                    # Classificação para o grupo todo
                    r_primeiro = items[0]["resultado"]
                    dep_nomes_batch = ["— selecione —"] + sorted(
                        d.descricao for d in db_batch.query(Departamento).all()
                    )
                    dep_pre = r_primeiro.departamento_nome
                    dep_idx_b = dep_nomes_batch.index(dep_pre) if dep_pre in dep_nomes_batch else 0

                    col_cls1, col_cls2, col_cls3 = st.columns(3)
                    with col_cls1:
                        dep_b = st.selectbox(
                            "Departamento", dep_nomes_batch,
                            index=dep_idx_b, key=f"batch_dep_{grupo_label}",
                        )
                    grp_b_id = None
                    cat_b_id = None
                    dep_b_id = None
                    if dep_b != "— selecione —":
                        dep_obj_b = db_batch.query(Departamento).filter(
                            Departamento.descricao == dep_b
                        ).first()
                        dep_b_id = dep_obj_b.id if dep_obj_b else None
                        grupos_b = (
                            db_batch.query(Grupo)
                            .filter(Grupo.departamento_id == dep_b_id)
                            .order_by(Grupo.descricao).all()
                        )
                        grp_nomes_b = ["— selecione —"] + [g.descricao for g in grupos_b]
                        grp_pre = r_primeiro.grupo_nome
                        grp_idx_b = grp_nomes_b.index(grp_pre) if grp_pre in grp_nomes_b else 0
                        with col_cls2:
                            grp_b = st.selectbox(
                                "Grupo", grp_nomes_b,
                                index=grp_idx_b, key=f"batch_grp_{grupo_label}",
                            )
                        if grp_b != "— selecione —":
                            grp_obj_b = next((g for g in grupos_b if g.descricao == grp_b), None)
                            grp_b_id = grp_obj_b.id if grp_obj_b else None
                            cats_b = (
                                db_batch.query(Categoria)
                                .filter(Categoria.grupo_id == grp_b_id)
                                .order_by(Categoria.descricao).all()
                            )
                            cat_nomes_b = ["— selecione —"] + [c.descricao for c in cats_b]
                            cat_pre = r_primeiro.categoria_nome
                            cat_idx_b = (
                                cat_nomes_b.index(cat_pre) if cat_pre in cat_nomes_b else 0
                            )
                            with col_cls3:
                                cat_b = st.selectbox(
                                    "Categoria", cat_nomes_b,
                                    index=cat_idx_b, key=f"batch_cat_{grupo_label}",
                                )
                            if cat_b != "— selecione —":
                                cat_obj_b = next(
                                    (c for c in cats_b if c.descricao == cat_b), None,
                                )
                                cat_b_id = cat_obj_b.id if cat_obj_b else None

                    # Botões de ação
                    col_act1, col_act2, col_act3 = st.columns([1, 1, 3])
                    with col_act1:
                        aprovar_sel = st.button(
                            f"Aprovar selecionados ({n_sel})",
                            type="primary",
                            disabled=(grp_b_id is None or n_sel == 0),
                            key=f"batch_aprovar_{grupo_label}",
                        )
                    with col_act2:
                        descartar_sel = st.button(
                            f"Sem categoria ({n_sel})",
                            disabled=(n_sel == 0),
                            key=f"batch_descartar_{grupo_label}",
                        )

                    if aprovar_sel:
                        db_batch.query(Produto).filter(Produto.id.in_(selected_ids)).update(
                            {
                                Produto.categoria_id: cat_b_id,
                                Produto.grupo_id: grp_b_id,
                                Produto.departamento_id: dep_b_id,
                                Produto.score_categoria: 1.0,
                                Produto.revisao_necessaria: False,
                                Produto.origem_padronizacao: "manual",
                            },
                            synchronize_session="fetch",
                        )
                        db_batch.commit()
                        _stats.clear()
                        st.success(f"{n_sel} produtos aprovados!")
                        st.rerun()

                    if descartar_sel:
                        db_batch.query(Produto).filter(Produto.id.in_(selected_ids)).update(
                            {
                                Produto.revisao_necessaria: False,
                                Produto.origem_padronizacao: "manual_sem_cat",
                            },
                            synchronize_session="fetch",
                        )
                        db_batch.commit()
                        _stats.clear()
                        st.success(f"{n_sel} produtos marcados como sem categoria.")
                        st.rerun()

    finally:
        db_batch.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ABA 3 — Marcas & Fabricantes
# ═══════════════════════════════════════════════════════════════════════════════

with aba_marcas:

    db2 = next(get_session())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _listar_fabricantes(db):
        return db.query(Fabricante).filter(Fabricante.ativo == True).order_by(Fabricante.nome).all()

    def _listar_marcas(db):
        return (
            db.query(Marca, Fabricante)
            .outerjoin(Fabricante, Marca.fabricante_id == Fabricante.id)
            .filter(Marca.ativo == True)
            .order_by(Marca.nome)
            .all()
        )

    def _salvar_fabricante(db, nome: str, cnpj: str, aliases_raw: str):
        nome = nome.strip().upper()
        if not nome:
            return False, "Nome obrigatório."
        aliases = [a.strip().upper() for a in aliases_raw.split(",") if a.strip()]
        fab = db.query(Fabricante).filter(Fabricante.nome == nome).first()
        if fab:
            return False, f"Fabricante '{nome}' já existe."
        fab = Fabricante(
            nome=nome,
            cnpj=cnpj.strip() or None,
            aliases=json.dumps(aliases) if aliases else None,
            ativo=True,
        )
        db.add(fab)
        db.commit()
        invalidar_cache_marcas()
        return True, f"Fabricante '{nome}' cadastrado."

    def _salvar_marca(db, nome: str, fabricante_id, categoria: str, aliases_raw: str):
        nome = nome.strip().upper()
        if not nome:
            return False, "Nome obrigatório."
        aliases = [a.strip().upper() for a in aliases_raw.split(",") if a.strip()]
        existing = db.query(Marca).filter(Marca.nome == nome).first()
        if existing:
            return False, f"Marca '{nome}' já existe."
        marca = Marca(
            nome=nome,
            fabricante_id=fabricante_id or None,
            categoria=categoria.strip().lower() or None,
            aliases=json.dumps(aliases) if aliases else None,
            ativo=True,
        )
        db.add(marca)
        db.commit()
        invalidar_cache_marcas()
        return True, f"Marca '{nome}' cadastrada."

    def _desativar_fabricante(db, fab_id: int):
        fab = db.query(Fabricante).filter(Fabricante.id == fab_id).first()
        if fab:
            fab.ativo = False
            db.commit()
            invalidar_cache_marcas()

    def _desativar_marca(db, marca_id: int):
        marca = db.query(Marca).filter(Marca.id == marca_id).first()
        if marca:
            marca.ativo = False
            db.commit()
            invalidar_cache_marcas()

    # ── Fabricantes ───────────────────────────────────────────────────────────

    st.subheader("Fabricantes")

    col_fab_form, col_fab_lista = st.columns([2, 3])

    with col_fab_form:
        with st.form("form_fabricante", clear_on_submit=True):
            st.markdown("**Novo fabricante**")
            fab_nome    = st.text_input("Nome *", placeholder="ex: UNILEVER")
            fab_cnpj    = st.text_input("CNPJ (opcional)", placeholder="14 dígitos sem máscara")
            fab_aliases = st.text_input(
                "Aliases (separados por vírgula)",
                placeholder="ex: UNILEVER BRASIL, UNILEVER BRF",
            )
            salvar_fab = st.form_submit_button("Cadastrar Fabricante", type="primary")

        if salvar_fab:
            ok, msg = _salvar_fabricante(db2, fab_nome, fab_cnpj, fab_aliases)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col_fab_lista:
        fabricantes = _listar_fabricantes(db2)
        if fabricantes:
            import pandas as pd
            df_fab = pd.DataFrame([
                {
                    "ID":   f.id,
                    "Nome": f.nome,
                    "CNPJ": f.cnpj or "—",
                    "Aliases": ", ".join(json.loads(f.aliases)) if f.aliases else "—",
                }
                for f in fabricantes
            ])
            st.dataframe(df_fab, use_container_width=True, hide_index=True)

            with st.expander("Desativar fabricante"):
                fab_opcoes = {f.nome: f.id for f in fabricantes}
                fab_del = st.selectbox("Fabricante", list(fab_opcoes.keys()), key="fab_del")
                if st.button("Desativar", key="btn_fab_del"):
                    _desativar_fabricante(db2, fab_opcoes[fab_del])
                    st.rerun()
        else:
            st.info("Nenhum fabricante cadastrado.")

    st.divider()

    # ── Marcas ────────────────────────────────────────────────────────────────

    st.subheader("Marcas")

    col_mrc_form, col_mrc_lista = st.columns([2, 3])

    with col_mrc_form:
        fabricantes_ativos = _listar_fabricantes(db2)
        fab_map = {"— nenhum —": None} | {f.nome: f.id for f in fabricantes_ativos}

        CATEGORIAS_DISPONIVEIS = [
            "— selecione —", "higiene", "limpeza", "bebidas",
            "frios", "laticinios", "panificacao", "graos", "alimentos",
        ]

        with st.form("form_marca", clear_on_submit=True):
            st.markdown("**Nova marca**")
            mrc_nome      = st.text_input("Nome *", placeholder="ex: DOVE")
            mrc_fab       = st.selectbox("Fabricante", list(fab_map.keys()))
            mrc_categoria = st.selectbox("Categoria", CATEGORIAS_DISPONIVEIS)
            mrc_aliases   = st.text_input(
                "Aliases (separados por vírgula)",
                placeholder="ex: DOVE ORIGINAL, DOVE MEN",
            )
            salvar_mrc = st.form_submit_button("Cadastrar Marca", type="primary")

        if salvar_mrc:
            fab_id   = fab_map[mrc_fab]
            cat_val  = "" if mrc_categoria == "— selecione —" else mrc_categoria
            ok, msg  = _salvar_marca(db2, mrc_nome, fab_id, cat_val, mrc_aliases)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col_mrc_lista:
        marcas = _listar_marcas(db2)
        if marcas:
            import pandas as pd
            df_mrc = pd.DataFrame([
                {
                    "ID":          m.id,
                    "Nome":        m.nome,
                    "Fabricante":  f.nome if f else "—",
                    "Categoria":   m.categoria or "—",
                    "Aliases":     ", ".join(json.loads(m.aliases)) if m.aliases else "—",
                }
                for m, f in marcas
            ])
            st.dataframe(df_mrc, use_container_width=True, hide_index=True)

            with st.expander("Desativar marca"):
                mrc_opcoes = {m.nome: m.id for m, _ in marcas}
                mrc_del = st.selectbox("Marca", list(mrc_opcoes.keys()), key="mrc_del")
                if st.button("Desativar", key="btn_mrc_del"):
                    _desativar_marca(db2, mrc_opcoes[mrc_del])
                    st.rerun()
        else:
            st.info("Nenhuma marca cadastrada.")

    db2.close()

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 4 — Tokens Desconhecidos
# ═══════════════════════════════════════════════════════════════════════════════

with aba_tokens:
    import pandas as pd
    from app.models.token_desconhecido import TokenDesconhecido

    db_tok = next(get_session())
    try:
        st.markdown(
            "Tokens encontrados nas descrições que **não foram reconhecidos** por "
            "nenhum dicionário do pipeline. Use esta lista para alimentar novas "
            "abreviações, marcas ou categorias via fila no CLAUDE.md."
        )

        total_tokens = db_tok.query(TokenDesconhecido).count()
        st.metric("Total de tokens únicos acumulados", total_tokens)
        st.divider()

        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            busca_token = st.text_input("Filtrar por token", placeholder="ex: SUCOS, NESTL...")
        with col_t2:
            min_contagem = st.number_input("Contagem mínima", min_value=1, value=2)

        q_tok = (
            db_tok.query(TokenDesconhecido)
            .filter(TokenDesconhecido.contagem >= min_contagem)
        )
        if busca_token:
            q_tok = q_tok.filter(
                TokenDesconhecido.token.ilike(f"%{busca_token.upper()}%")
            )
        tokens_rows = q_tok.order_by(TokenDesconhecido.contagem.desc()).limit(500).all()

        if not tokens_rows:
            st.info("Nenhum token desconhecido encontrado com os filtros aplicados.")
        else:
            df_tok = pd.DataFrame([
                {
                    "Token":          r.token,
                    "Ocorrências":    r.contagem,
                    "Primeiro visto": r.primeiro_visto.strftime("%d/%m/%Y") if r.primeiro_visto else "—",
                    "Último visto":   r.ultimo_visto.strftime("%d/%m/%Y") if r.ultimo_visto else "—",
                    "Exemplo":        r.exemplo or "—",
                }
                for r in tokens_rows
            ])
            st.dataframe(
                df_tok,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ocorrências": st.column_config.ProgressColumn(
                        format="%d",
                        min_value=0,
                        max_value=int(df_tok["Ocorrências"].max()) if len(df_tok) else 1,
                    ),
                    "Exemplo": st.column_config.TextColumn(width="large"),
                },
            )
            st.caption(f"{len(tokens_rows)} tokens exibidos (limite 500)")

        st.divider()
        with st.expander("⚠️ Limpar tokens com contagem = 1 (ruído)"):
            st.warning("Remove todos os tokens vistos apenas uma vez — geralmente são ruído ou erros de digitação.")
            if st.button("Limpar tokens únicos", type="primary"):
                deleted = (
                    db_tok.query(TokenDesconhecido)
                    .filter(TokenDesconhecido.contagem == 1)
                    .delete()
                )
                db_tok.commit()
                st.success(f"{deleted} tokens removidos.")
                st.rerun()

    finally:
        db_tok.close()

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 5 — Clientes & Upload
# ═══════════════════════════════════════════════════════════════════════════════

with aba_clientes:

    brt = timezone(timedelta(hours=-3))

    # ── Seção A: lista de tenants ─────────────────────────────────────────────

    st.subheader("Clientes cadastrados")

    from sqlalchemy.orm import joinedload
    from app.models.grupo_empresarial import GrupoEmpresarial

    db_cli = next(get_session())
    try:
        tenants = (
            db_cli.query(Tenant)
            .options(joinedload(Tenant.grupo))
            .order_by(Tenant.nome)
            .all()
        )
    finally:
        db_cli.close()

    if tenants:
        st.dataframe(
            [
                {
                    "ID":             t.id,
                    "Nome":           t.nome,
                    "CNPJ":           formatar_cnpj(t.cnpj),
                    "Código acesso":  t.codigo_acesso or "—",
                    "Senha":          "✓" if t.senha_hash else "✗ sem senha",
                    "Grupo":          t.grupo.nome if t.grupo else "—",
                    "Ativo":          "✓" if t.ativo else "✗",
                    "Criado em":      t.criado_em.strftime("%d/%m/%Y") if t.criado_em else "—",
                }
                for t in tenants
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum cliente cadastrado.")

    st.divider()

    # ── Seção A2: editar cliente existente ────────────────────────────────────

    st.subheader("Editar cliente")

    if tenants:
        tenant_edit_opts = {f"{t.nome} ({formatar_cnpj(t.cnpj)})": t for t in tenants}
        tenant_edit_sel  = st.selectbox("Selecione o cliente", list(tenant_edit_opts.keys()), key="edit_sel")
        t_edit = tenant_edit_opts[tenant_edit_sel]

        with st.form("form_editar_tenant"):
            db_grp_edit = next(get_session())
            try:
                grupos_edit = TenantService(db_grp_edit).listar_grupos()
            finally:
                db_grp_edit.close()

            grupo_opts_edit  = {"— nenhum —": None} | {g.nome: g.id for g in grupos_edit}
            grupo_atual_nome = t_edit.grupo.nome if t_edit.grupo else "— nenhum —"

            nome_edit    = st.text_input("Nome *", value=t_edit.nome)
            cnpj_edit    = st.text_input("CNPJ *", value=formatar_cnpj(t_edit.cnpj))
            codigo_edit  = st.text_input("Código de acesso", value=t_edit.codigo_acesso or "")
            grupo_e_sel  = st.selectbox(
                "Grupo Empresarial",
                list(grupo_opts_edit.keys()),
                index=list(grupo_opts_edit.keys()).index(grupo_atual_nome) if grupo_atual_nome in grupo_opts_edit else 0,
            )
            ativo_edit   = st.checkbox("Ativo", value=t_edit.ativo)
            salvar_edit  = st.form_submit_button("Salvar alterações", type="primary")

        if salvar_edit:
            cnpj_limpo_e = limpar_cnpj(cnpj_edit)
            if not nome_edit.strip():
                st.error("Nome obrigatório.")
            elif len(cnpj_limpo_e) != 14:
                st.error("CNPJ deve ter 14 dígitos numéricos.")
            else:
                db_e = next(get_session())
                try:
                    t = db_e.query(Tenant).filter(Tenant.id == t_edit.id).first()
                    t.nome          = nome_edit.strip()
                    t.cnpj          = cnpj_limpo_e
                    t.codigo_acesso = codigo_edit.strip() or None
                    t.ativo         = ativo_edit
                    t.grupo_id      = grupo_opts_edit.get(grupo_e_sel)
                    db_e.commit()
                    st.success("Cliente atualizado com sucesso.")
                    st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "UNIQUE" in msg.upper():
                        st.error("CNPJ ou código de acesso já está em uso por outro cliente.")
                    else:
                        st.error(f"Erro: {msg}")
                finally:
                    db_e.close()

    st.divider()

    # ── Seção B: cadastrar novo tenant ────────────────────────────────────────

    st.subheader("Cadastrar novo cliente")

    db_grp_b = next(get_session())
    try:
        grupos_b = TenantService(db_grp_b).listar_grupos()
    finally:
        db_grp_b.close()

    grupo_opts_b = {"— nenhum —": None} | {g.nome: g.id for g in grupos_b}

    with st.form("form_novo_tenant", clear_on_submit=True):
        nome_novo       = st.text_input("Nome *")
        cnpj_novo       = st.text_input("CNPJ *", placeholder="14 dígitos (com ou sem máscara)")
        col_s1, col_s2 = st.columns(2)
        senha_nova      = col_s1.text_input("Senha *", type="password")
        senha_nova2     = col_s2.text_input("Confirmar senha *", type="password")
        codigo_novo     = st.text_input("Código de acesso (opcional)", placeholder="ex: GS01 — letras e números, único")
        grupo_sel_nome  = st.selectbox("Grupo Empresarial (opcional)", list(grupo_opts_b.keys()))
        cadastrar       = st.form_submit_button("Cadastrar", type="primary")

    if cadastrar:
        cnpj_limpo = limpar_cnpj(cnpj_novo)
        if not nome_novo.strip():
            st.error("Nome obrigatório.")
        elif len(cnpj_limpo) != 14:
            st.error("CNPJ deve ter 14 dígitos numéricos.")
        elif not senha_nova:
            st.error("Senha obrigatória.")
        elif senha_nova != senha_nova2:
            st.error("As senhas não coincidem.")
        else:
            db_cad = next(get_session())
            try:
                svc_cad = TenantService(db_cad)
                novo = svc_cad.criar(
                    nome_novo.strip(),
                    cnpj_limpo,
                    senha=senha_nova,
                    codigo_acesso=codigo_novo.strip() or None,
                )
                grupo_id_sel = grupo_opts_b.get(grupo_sel_nome)
                if grupo_id_sel:
                    svc_cad.associar_tenant_a_grupo(novo.id, grupo_id_sel)
                st.success(f"Cliente **{nome_novo.strip()}** cadastrado com sucesso.")
                st.rerun()
            except Exception as e:
                msg = str(e)
                if "UNIQUE" in msg.upper():
                    st.error("CNPJ ou código de acesso já cadastrado.")
                else:
                    st.error(f"Erro: {msg}")
            finally:
                db_cad.close()

    st.divider()

    # ── Seção B2: definir/redefinir senha de tenant existente ─────────────────

    st.subheader("Definir / redefinir senha")

    db_sen = next(get_session())
    try:
        tenants_sen = db_sen.query(Tenant).filter(Tenant.ativo == True).order_by(Tenant.nome).all()
    finally:
        db_sen.close()

    tenant_sen_opts = {f"{t.nome} ({formatar_cnpj(t.cnpj)})": t.id for t in tenants_sen}

    with st.form("form_def_senha", clear_on_submit=True):
        tenant_sen_sel  = st.selectbox("Cliente", list(tenant_sen_opts.keys()))
        codigo_sen      = st.text_input("Código de acesso (opcional — deixe em branco para não alterar)")
        col_p1, col_p2 = st.columns(2)
        nova_senha      = col_p1.text_input("Nova senha *", type="password")
        nova_senha2     = col_p2.text_input("Confirmar nova senha *", type="password")
        salvar_senha    = st.form_submit_button("Salvar", type="primary")

    if salvar_senha:
        if not nova_senha:
            st.error("Senha obrigatória.")
        elif nova_senha != nova_senha2:
            st.error("As senhas não coincidem.")
        else:
            tid = tenant_sen_opts[tenant_sen_sel]
            db_s = next(get_session())
            try:
                svc_s = TenantService(db_s)
                svc_s.definir_senha(tid, nova_senha)
                if codigo_sen.strip():
                    t = svc_s.buscar_por_id(tid)
                    t.codigo_acesso = codigo_sen.strip()
                    db_s.commit()
                st.success("Senha atualizada com sucesso.")
            except Exception as e:
                msg = str(e)
                if "UNIQUE" in msg.upper():
                    st.error("Código de acesso já está em uso por outro cliente.")
                else:
                    st.error(f"Erro: {msg}")
            finally:
                db_s.close()

    st.divider()

    # ── Seção C: upload admin ─────────────────────────────────────────────────

    st.subheader("Upload de arquivos EFD")

    db_up = next(get_session())
    try:
        svc_up = TenantService(db_up)
        tenants_ativos = db_up.query(Tenant).filter(Tenant.ativo == True).order_by(Tenant.nome).all()
        grupos_up = svc_up.listar_grupos()
    finally:
        db_up.close()

    if not tenants_ativos:
        st.warning("Nenhum cliente ativo. Cadastre um cliente primeiro.")
        st.stop()

    # Filtro por grupo
    if grupos_up:
        grupo_up_opts = {"Todos os clientes": None} | {g.nome: g.id for g in grupos_up}
        grupo_up_sel = st.selectbox("Filtrar por grupo", list(grupo_up_opts.keys()), key="admin_upload_grupo")
        grupo_up_id = grupo_up_opts[grupo_up_sel]
        if grupo_up_id:
            tenants_ativos = [t for t in tenants_ativos if t.grupo_id == grupo_up_id]

    opcoes_tenant = {t.nome: {"id": t.id, "cnpj": t.cnpj} for t in tenants_ativos}

    tenant_selecionado_nome = st.selectbox(
        "Tenant de destino",
        list(opcoes_tenant.keys()),
        key="admin_upload_tenant_nome",
    )
    tenant_selecionado_id   = opcoes_tenant[tenant_selecionado_nome]["id"]
    tenant_selecionado_cnpj = opcoes_tenant[tenant_selecionado_nome]["cnpj"]

    arquivos_admin = st.file_uploader(
        "Selecione os arquivos EFD (.txt)",
        type=["txt"],
        accept_multiple_files=True,
        key="admin_upload_files",
        help="Arquivos SPED Fiscal no formato .txt gerado pelo SPED",
    )

    if arquivos_admin:
        st.subheader(f"{len(arquivos_admin)} arquivo(s) selecionado(s)")
        st.divider()

        metadados_lista = []
        erro_upload = False

        for arquivo in arquivos_admin:
            conteudo = arquivo.read().decode("latin-1")
            try:
                metadados = processar_renomeacao(conteudo, arquivo.name)
                metadados['conteudo'] = conteudo

                cnpj_arquivo = limpar_cnpj(metadados['cnpj'])
                cnpj_tenant  = limpar_cnpj(tenant_selecionado_cnpj)
                cnpj_ok = cnpj_arquivo == cnpj_tenant

                if not cnpj_ok:
                    st.error(
                        f"**{arquivo.name}** — CNPJ do arquivo "
                        f"(`{formatar_cnpj(cnpj_arquivo)}`) não bate com o tenant selecionado "
                        f"(`{formatar_cnpj(cnpj_tenant)}`). Arquivo ignorado."
                    )
                    erro_upload = True
                    continue

                metadados_lista.append(metadados)

                with st.expander(f"{metadados['razao_social']} — {metadados['periodo_ini']} a {metadados['periodo_fin']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Empresa:** {metadados['razao_social']}")
                        st.info(f"**CNPJ do arquivo:** {formatar_cnpj(metadados['cnpj'])}")
                        st.info(f"**UF:** {metadados['uf']}")
                    with col2:
                        st.info(f"**Período:** {metadados['periodo_ini']} a {metadados['periodo_fin']}")
                        st.info(f"**Nome original:** {metadados['nome_original']}")
                        st.info(f"**Nome padronizado:** {metadados['novo_nome']}")
            except ValueError as e:
                st.error(f"Erro em {arquivo.name}: {str(e)}")
                erro_upload = True

        st.divider()

        if not erro_upload:
            if st.button("Confirmar e processar todos", type="primary", use_container_width=True, key="admin_upload_btn"):

                db_proc = next(get_session())
                resultados = []

                for metadados in metadados_lista:
                    bronze = BronzeProcessor(db_proc, tenant_selecionado_id)

                    if bronze.arquivo_ja_ingerido(metadados['novo_nome']):
                        resultados.append({
                            "arquivo": metadados['novo_nome'],
                            "status": "ignorado",
                        })
                        continue

                    caminho = os.path.join("storage", "arquivos", metadados['novo_nome'])
                    with open(caminho, "w", encoding="latin-1") as f:
                        f.write(metadados['conteudo'])

                    registro = ArquivoImportado(
                        tenant_id       = tenant_selecionado_id,
                        nome_original   = metadados['nome_original'],
                        nome_padronizado= metadados['novo_nome'],
                        cnpj            = metadados['cnpj'],
                        periodo_ini     = metadados['periodo_ini'],
                        periodo_fin     = metadados['periodo_fin'],
                        status          = "processando",
                    )
                    db_proc.add(registro)
                    db_proc.commit()

                    with st.spinner(f"Bronze: {metadados['novo_nome']}..."):
                        try:
                            resultado_bronze = bronze.ingerir(metadados['conteudo'], metadados['novo_nome'])
                            registro.status = "bronze_concluido"
                            db_proc.commit()
                        except Exception as e:
                            registro.status = "erro"
                            registro.erro_msg = str(e)
                            db_proc.commit()
                            resultados.append({"arquivo": metadados['novo_nome'], "status": "erro", "erro": str(e)})
                            continue

                    with st.spinner(f"Silver: {metadados['novo_nome']}..."):
                        try:
                            silver = SilverProcessor(db_proc, tenant_selecionado_id)
                            resultado_silver = silver.processar(metadados['novo_nome'])
                            registro.status = "concluido"
                            registro.processado_em = datetime.utcnow()
                            db_proc.commit()
                            resultados.append({
                                "arquivo":             metadados['novo_nome'],
                                "status":              "concluido",
                                "linhas_bronze":       resultado_bronze['linhas'],
                                "documentos":          resultado_silver['documentos'],
                                "itens":               resultado_silver['itens'],
                                "produtos_criados":    resultado_silver['produtos_criados'],
                                "produtos_atualizados":resultado_silver['produtos_atualizados'],
                            })
                        except Exception as e:
                            registro.status = "erro"
                            registro.erro_msg = str(e)
                            db_proc.commit()
                            resultados.append({"arquivo": metadados['novo_nome'], "status": "erro", "erro": str(e)})

                db_proc.close()

                st.divider()
                st.subheader("Resultado")
                for r in resultados:
                    if r['status'] == 'concluido':
                        st.success(
                            f"✓ **{r['arquivo']}** — "
                            f"{r['documentos']} docs · {r['itens']} itens · "
                            f"{r['produtos_criados']} produtos novos · {r['produtos_atualizados']} atualizados"
                        )
                    elif r['status'] == 'ignorado':
                        st.warning(f"⚠ **{r['arquivo']}** — já importado anteriormente, ignorado.")
                    else:
                        st.error(f"✗ **{r['arquivo']}** — {r.get('erro', 'erro desconhecido')}")

    st.divider()

    # ── Seção D: gestão de grupos empresariais ────────────────────────────────

    st.subheader("Grupos Empresariais")

    col_grp_lista, col_grp_form = st.columns([3, 2])

    with col_grp_lista:
        db_gd = next(get_session())
        try:
            grupos_d = TenantService(db_gd).listar_grupos()
            tenants_d = db_gd.query(Tenant).options(joinedload(Tenant.grupo)).order_by(Tenant.nome).all()
        finally:
            db_gd.close()

        if grupos_d:
            lojas_por_grupo = {}
            for t in tenants_d:
                gid = t.grupo_id
                if gid:
                    lojas_por_grupo.setdefault(gid, []).append(t.nome)

            st.dataframe(
                [
                    {
                        "ID":        g.id,
                        "Nome":      g.nome,
                        "Lojas":     ", ".join(lojas_por_grupo.get(g.id, [])) or "—",
                        "Criado em": g.criado_em.strftime("%d/%m/%Y") if g.criado_em else "—",
                    }
                    for g in grupos_d
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhum grupo cadastrado.")

    with col_grp_form:
        st.caption("Criar novo grupo")
        with st.form("form_novo_grupo", clear_on_submit=True):
            nome_grupo = st.text_input("Nome do grupo *")
            criar_grp  = st.form_submit_button("Criar", type="primary")

        if criar_grp:
            if not nome_grupo.strip():
                st.error("Nome obrigatório.")
            else:
                db_cg = next(get_session())
                try:
                    TenantService(db_cg).criar_grupo(nome_grupo.strip())
                    st.success(f"Grupo **{nome_grupo.strip()}** criado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    db_cg.close()

    with st.expander("Associar loja a grupo"):
        db_assoc = next(get_session())
        try:
            svc_assoc    = TenantService(db_assoc)
            tenants_assoc = db_assoc.query(Tenant).filter(Tenant.ativo == True).order_by(Tenant.nome).all()
            grupos_assoc  = svc_assoc.listar_grupos()
        finally:
            db_assoc.close()

        if not tenants_assoc or not grupos_assoc:
            st.info("Cadastre pelo menos um cliente e um grupo antes de associar.")
        else:
            col_a, col_b, col_c = st.columns([2, 2, 1])
            with col_a:
                tenant_assoc_nome = st.selectbox(
                    "Loja", [t.nome for t in tenants_assoc], key="assoc_tenant"
                )
            with col_b:
                grupo_assoc_nome = st.selectbox(
                    "Grupo", [g.nome for g in grupos_assoc], key="assoc_grupo"
                )
            with col_c:
                st.write("")
                st.write("")
                associar_btn = st.button("Associar", use_container_width=True)

            if associar_btn:
                tenant_sel = next(t for t in tenants_assoc if t.nome == tenant_assoc_nome)
                grupo_sel  = next(g for g in grupos_assoc  if g.nome == grupo_assoc_nome)
                db_a = next(get_session())
                try:
                    TenantService(db_a).associar_tenant_a_grupo(tenant_sel.id, grupo_sel.id)
                    st.success(f"**{tenant_assoc_nome}** associada ao grupo **{grupo_assoc_nome}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    db_a.close()
