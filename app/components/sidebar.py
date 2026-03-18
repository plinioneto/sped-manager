import streamlit as st

def render_sidebar():
    st.sidebar.title (f'{st.session_state.tenant_nome}')
    st.sidebar.divider()

    st.sidebar.page_link("app/main.py", label="Início")
    st.sidebar.page_link("app/pages/01_dashboard.py", label="Dashboard")
    st.sidebar.page_link("app/pages/02_upload_sped.py", label="Upload SPED")
    st.sidebar.page_link("app/pages/03_estoque.py", label="Estoque")
    st.sidebar.page_link("app/pages/04_relatorios.py", label="Relatórios")
    st.sidebar.page_link("app/pages/05_configuracoes.py", label="Configurações")

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.tenant_id = None
        st.session_state.tenant_nome = None
        st.rerun()