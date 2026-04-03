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

import streamlit as st

from app.utils.db import get_session
from app.models.produto import Produto
from app.models.tenant import Tenant
from app.models.categoria import Departamento, Grupo, Categoria
from app.models.fabricante import Fabricante
from app.models.marca import Marca
from app.services.produto_padronizacao import processar_descricao
from app.services.produto_padronizacao.categorizador import invalidar_cache
from app.services.produto_padronizacao.identificador import invalidar_cache_marcas

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

aba_revisao, aba_batch, aba_marcas, aba_tokens = st.tabs([
    "Revisão Individual", "Revisão em Lote", "Marcas & Fabricantes", "Tokens Desconhecidos",
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
