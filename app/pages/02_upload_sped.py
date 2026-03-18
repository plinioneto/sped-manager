import streamlit as st
from app.components.sidebar import render_sidebar

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Upload SPED")
st.divider()

arquivo = st.file_uploader(
    "Selecione o arquivo SPED",
    type=["txt"],
    help="Arquivo SPED Fiscal ou Contribuições no formato .txt"
)

if arquivo:
    st.success(f"Arquivo recebido: {arquivo.name}")
    st.info("Processamento via parser será integrado em breve.")