import streamlit as st
from app.utils.db import get_session, engine
from app.models.base import Base, init_db

# Criar tabelas no banco caso não existam
Base.metadata.create_all(bind=engine)

# Config da página
st.set_page_config(
    page_title="SPED Manager",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificação se usuário está logado
if "tenant_id" not in st.session_state:
    st.session_state.tenant_id = None

if "tenant_nome" not in st.session_state:
    st.session_state.tenant_nome = None

# Guard de autenticação - bloqueia acesso sem login
if not st.session_state.tenant_id:
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
        tenants = service.listar()

        tenant = next((t for t in tenants if t.cnpj == cnpj), None)

        if tenant:
            st.session_state.tenant_id = tenant.id
            st.session_state.tenant_nome = tenant.nome
            st.rerun()
        else:
            st.error("CNPJ não encontrado")
else:
    # sucesso no login

    st.sidebar.title(f"🏚 {st.session_state.tenant_nome}")
    st.sidebar.divider()

    if st.sidebar.button("Sair"):
        st.session_state.tenant_id = None
        st.session_state.tenant_nome = None
        st.rerun()

    st.title("Bem vindo ao SPED Manager")
    st.write("Selecione uma opção no menu lateral.")
