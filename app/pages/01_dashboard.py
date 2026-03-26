import streamlit as st
from sqlalchemy import func
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.produto import Produto
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.arquivo_importado import ArquivoImportado

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

ultimos_arquivos = (
    db.query(ArquivoImportado)
    .filter(ArquivoImportado.tenant_id == tenant_id)
    .order_by(ArquivoImportado.criado_em.desc())
    .limit(10)
    .all()
)

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

st.divider()
st.subheader("Últimos arquivos importados")

if not ultimos_arquivos:
    st.info("Nenhum arquivo importado ainda.")
else:
    for arq in ultimos_arquivos:
        periodo = f"{arq.periodo_ini[:4]}-{arq.periodo_ini[4:6]} → {arq.periodo_fin[:4]}-{arq.periodo_fin[4:6]}"
        from datetime import timezone, timedelta
        brt = timezone(timedelta(hours=-3))
        data = arq.criado_em.replace(tzinfo=timezone.utc).astimezone(brt).strftime("%d/%m/%Y %H:%M") if arq.criado_em else "—"
        status_icon = "✅" if arq.status == "concluido" else ("❌" if arq.status == "erro" else "⏳")

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.write(f"**{arq.nome_padronizado}**")
            c2.write(f"Período: {periodo}")
            c3.write(f"Importado em: {data}")
            c4.write(f"{status_icon} {arq.status}")
