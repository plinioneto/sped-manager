import streamlit as st
import pandas as pd
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.services.importacao_service import ImportacaoService

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Upload SPED")
st.divider()

st.subheader("Importar arquivos do parser")
st.caption("Exporte as tabelas do Databricks como CSV e faça o upload aqui.")

col1, col2 = st.columns(2)

with col1:
    arquivo_0200 = st.file_uploader("Tabela 0200 (produtos)", type=["csv"], key="f0200")
    arquivo_c100 = st.file_uploader("Tabela C100 (documentos)", type=["csv"], key="fc100")

with col2:
    arquivo_c170 = st.file_uploader("Tabela C170 (itens)", type=["csv"], key="fc170")
    arquivo_c190 = st.file_uploader("Tabela C190 (ICMS)", type=["csv"], key="fc190")

st.divider()

if st.button("Importar", type="primary", use_container_width=True):
    if not arquivo_0200 or not arquivo_c100 or not arquivo_c170:
        st.error("Envie pelo menos os arquivos 0200, C100 e C170.")
    else:
        with st.spinner("Importando dados..."):
            try:
                df_0200 = pd.read_csv(arquivo_0200, sep=",", dtype=str)
                df_c100 = pd.read_csv(arquivo_c100, sep=",", dtype=str)
                df_c170 = pd.read_csv(arquivo_c170, sep=",", dtype=str)

                db = next(get_session())
                service = ImportacaoService(db, st.session_state.tenant_id)

                qtd_produtos = service.importar_produtos(df_0200)
                qtd_docs = service.importar_documentos(df_c100, df_c170)

                st.success(f"Importação concluída! {qtd_produtos} produtos e {qtd_docs} documentos importados.")

            except Exception as e:
                st.error(f"Erro na importação: {str(e)}")