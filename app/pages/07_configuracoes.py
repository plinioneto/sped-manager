import streamlit as st
import app.models
from app.components.sidebar import render_sidebar

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Configurações")
st.divider()
st.info("Módulo de configurações em desenvolvimento.")