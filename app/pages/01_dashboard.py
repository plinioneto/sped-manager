import streamlit as st
from sqlalchemy import func
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.produto import Produto
from app.models.itens_fiscal_c170 import ItemFiscal

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Dashboard")
st.divider()

tenant_id = st.session_state.tenant_id

db = next(get_session())

total_notas = (
    db.query(func.count(DocumentoFiscal.id))
    .filter(DocumentoFiscal.tenant_id == tenant_id)
    .scalar()
) or 0

total_produtos = (
    db.query(func.count(Produto.id))
    .filter(Produto.tenant_id == tenant_id)
    .scalar()
) or 0

valor_total = (
    db.query(func.sum(DocumentoFiscal.vl_doc))
    .filter(DocumentoFiscal.tenant_id == tenant_id)
    .scalar()
) or 0.0

total_itens = (
    db.query(func.count(ItemFiscal.id))
    .filter(ItemFiscal.tenant_id == tenant_id)
    .scalar()
) or 0

db.close()

col1, col2 = st.columns(2)

with col1:
    st.metric(
        label="Notas fiscais importadas",
        value=f"{total_notas:,}".replace(",", "."),
        help="Total de documentos fiscais (bloco C100)"
    )

with col2:
    st.metric(
        label="Produtos cadastrados",
        value=f"{total_produtos:,}".replace(",", "."),
        help="Total de produtos no cadastro (bloco 0200)"
    )

col3, col4 = st.columns(2)

with col3:
    valor_formatado = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.metric(
        label="Valor total das notas",
        value=valor_formatado,
        help="Soma do campo vl_doc de todos os documentos fiscais"
    )

with col4:
    st.metric(
        label="Itens de notas fiscais",
        value=f"{total_itens:,}".replace(",", "."),
        help="Total de itens nas notas fiscais (bloco C170)"
    )
