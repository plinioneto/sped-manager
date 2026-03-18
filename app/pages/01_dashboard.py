import streamlit as st
from app.components.sidebar import render_sidebar

# redireciona para login caso não esteja autenticado
if not st.session_state.get('tenant_id'):
    st.switch_page('app/main.py')

render_sidebar()

st.title('Dashboard')
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Documentos fiscais", value="0")

with col2:
    st.metric(label="Produtos cadastrados", value="0")

with col3:
    st.metric(label="Último SPED importado", value="—")

st.divider()
st.info("Importe um arquivo SPED para começar a visualizar os dados.")