import streamlit as st

def render_sidebar():

    # esconde a navegação automática do Streamlit
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.title(f"🛒 {st.session_state.tenant_nome}")
    st.sidebar.divider()

    st.sidebar.page_link("pages/01_dashboard.py", label="Dashboard")
    st.sidebar.page_link("pages/02_upload_sped.py", label="Upload SPED")
    st.sidebar.page_link("pages/03_estoque.py", label="Estoque")
    st.sidebar.page_link("pages/04_relatorios.py", label="Relatórios")
    st.sidebar.page_link("pages/05_configuracoes.py", label="Configurações")

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.tenant_id = None
        st.session_state.tenant_nome = None
        st.rerun()