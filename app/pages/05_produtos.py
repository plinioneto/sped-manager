import streamlit as st
import pandas as pd
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.models.produto import Produto

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

tenant_id = st.session_state.tenant_id

st.title("Cadastro de Produtos")
st.divider()

db = next(get_session())

try:
    produtos = (
        db.query(Produto)
        .filter(Produto.tenant_id == tenant_id)
        .order_by(Produto.descr_item)
        .all()
    )
finally:
    db.close()

if not produtos:
    st.info("Nenhum produto cadastrado. Importe um arquivo EFD para popular o cadastro.")
    st.stop()

# --- métricas ---
col1, col2, col3 = st.columns(3)
col1.metric("Total de produtos", f"{len(produtos):,}".replace(",", "."))

tipos = sorted({p.tipo_item for p in produtos if p.tipo_item})
ncms = sorted({p.cod_ncm for p in produtos if p.cod_ncm})

ativos = sum(1 for p in produtos if p.ativo)
col2.metric("Ativos", f"{ativos:,}".replace(",", "."))
col3.metric("Tipos de item", str(len(tipos)))

st.divider()

# --- filtros ---
cf1, cf2, cf3 = st.columns([3, 1, 1])

busca = cf1.text_input("Buscar por código ou descrição", placeholder="Digite o código ou descrição...")

tipo_opcoes = ["Todos"] + tipos
tipo_sel = cf2.selectbox("Tipo de item", tipo_opcoes)

ncm_opcoes = ["Todos"] + ncms
ncm_sel = cf3.selectbox("NCM", ncm_opcoes)

# --- aplicar filtros ---
filtrados = produtos

if busca:
    termo = busca.lower()
    filtrados = [
        p for p in filtrados
        if termo in (p.cod_item or "").lower() or termo in (p.descr_item or "").lower()
    ]

if tipo_sel != "Todos":
    filtrados = [p for p in filtrados if p.tipo_item == tipo_sel]

if ncm_sel != "Todos":
    filtrados = [p for p in filtrados if p.cod_ncm == ncm_sel]

st.caption(f"{len(filtrados)} produto(s) encontrado(s)")

# --- tabela ---
TIPO_ITEM = {
    "00": "Mercadoria para Revenda",
    "01": "Matéria-Prima",
    "02": "Embalagem",
    "03": "Produto em Processo",
    "04": "Produto Acabado",
    "05": "Subproduto",
    "06": "Produto Intermediário",
    "07": "Material de Uso e Consumo",
    "08": "Ativo Imobilizado",
    "09": "Serviços",
    "10": "Outros Insumos",
    "99": "Outras",
}

rows = []
for p in filtrados:
    rows.append({
        "Código": p.cod_item,
        "Descrição": p.descr_item,
        "Cód. Barras": p.cod_barra or "—",
        "Unidade": p.unid_inv or "—",
        "Tipo": TIPO_ITEM.get(p.tipo_item, p.tipo_item or "—"),
        "NCM": p.cod_ncm or "—",
        "CEST": p.cest or "—",
        "Alíq. ICMS (%)": p.aliq_icms if p.aliq_icms is not None else "—",
        "Ativo": "Sim" if p.ativo else "Não",
    })

df = pd.DataFrame(rows)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Alíq. ICMS (%)": st.column_config.NumberColumn(format="%.2f"),
    },
)
