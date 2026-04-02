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

aba_revisao, aba_marcas = st.tabs(["Revisão de Produtos", "Marcas & Fabricantes"])

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

    def _pendentes(db, filtro_tenant, apenas_sem_categoria, apenas_revisao, limit=200):
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

    tenants      = [t.nome for t in db.query(Tenant).order_by(Tenant.nome).all()]
    departamentos = db.query(Departamento).order_by(Departamento.descricao).all()

    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        filtro_tenant = st.selectbox("Cliente", ["Todos"] + tenants, key="filtro_tenant")
    with col_f2:
        modo = st.radio(
            "Filtrar por",
            ["Sem categoria + revisão", "Sem categoria", "Revisão necessária"],
            horizontal=True,
        )
    with col_f3:
        st.write("")

    apenas_sem_cat = (modo == "Sem categoria")
    apenas_revisao = (modo == "Revisão necessária")
    filtro_t       = None if filtro_tenant == "Todos" else filtro_tenant

    pendentes = _pendentes(db, filtro_t, apenas_sem_cat, apenas_revisao)

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
                st.rerun()

        with col_b2:
            if st.button("Pular", use_container_width=True):
                st.session_state.rev_idx += 1
                st.rerun()

        with col_b3:
            if st.button("Sem categoria", use_container_width=True,
                         help="Marca como revisado mas sem categoria"):
                _salvar_classificacao(db, produto.id, None, None, None, descarta=True)
                _stats.clear()
                st.session_state.rev_idx += 1
                st.rerun()

        with col_b4:
            if st.button("Sair", use_container_width=True):
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
# ABA 2 — Marcas & Fabricantes
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
