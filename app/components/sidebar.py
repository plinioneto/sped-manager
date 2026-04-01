import streamlit as st
from app.utils.formatters import formatar_cnpj

def render_sidebar():
    # esconde a navegação automática do Streamlit
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.title(f"🏪 {st.session_state.tenant_nome}")
    st.sidebar.caption(formatar_cnpj(st.session_state.tenant_cnpj))
    st.sidebar.divider()

    st.sidebar.page_link("pages/00_inicio.py", label="Início")
    st.sidebar.page_link("pages/01_gestao_vendas.py", label="Gestão de Vendas")
    st.sidebar.page_link("pages/02_compras.py", label="Gestão de Compras")
    st.sidebar.page_link("pages/03_gestao_fiscal.py", label="Gestão Fiscal")
    st.sidebar.page_link("pages/04_inventario.py", label="Estoque & Inventário")
    st.sidebar.page_link("pages/05_produtos.py", label="Cadastro de Produtos")
    st.sidebar.page_link("pages/06_dados.py", label="Dados")
    st.sidebar.page_link("pages/07_configuracoes.py", label="Configurações")

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.tenant_id = None
        st.session_state.tenant_nome = None
        st.session_state.tenant_cnpj = None
        st.rerun()