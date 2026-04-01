import streamlit as st
from app.utils.db import get_session, engine
from app.models.base import Base
import app.models

# Criar tabelas no banco caso não existam
Base.metadata.create_all(bind=engine)

# Config da página
st.set_page_config(
    page_title="SPED Manager",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# esconde navegação automática do Streamlit em todas as situações
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# Verificação se usuário está logado
if "tenant_id" not in st.session_state:
    st.session_state.tenant_id = None

if "tenant_nome" not in st.session_state:
    st.session_state.tenant_nome = None

if "tenant_cnpj" not in st.session_state:
    st.session_state.tenant_cnpj = None

# Guard de autenticação - bloqueia acesso sem login
if not st.session_state.tenant_id:
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="collapsedControl"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

    st.title('SPED Manager')
    st.subheader('Acesse sua conta')

    with st.form('login_form'):
        cnpj = st.text_input("CNPJ")
        senha = st.text_input("Senha", type = "password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        # autenticação temporária que será substituída quando criar o model de usuário (tabela)
        db = next(get_session())
        from app.services.tenant_service import TenantService
        service = TenantService(db)
        tenant = service.buscar_por_cnpj(cnpj)

        if tenant:
            st.session_state.tenant_id = tenant.id
            st.session_state.tenant_nome = tenant.nome
            st.session_state.tenant_cnpj = tenant.cnpj
            st.rerun()
        else:
            st.error("CNPJ não encontrado")
else:
    # sucesso no login

    from app.components.sidebar import render_sidebar
    render_sidebar()
    st.switch_page("pages/01_gestao_vendas.py")

    st.title("Bem vindo ao SPED Manager")
    st.write("Selecione uma opção no menu lateral.")
