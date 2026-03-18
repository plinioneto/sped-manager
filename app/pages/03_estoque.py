import streamlit as st
from app.components.sidebar import render_sidebar

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Estoque")
st.divider()
st.info("Módulo de estoque em desenvolvimento.")