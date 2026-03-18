import streamlit as st
import os
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.parser.renomeador import processar_renomeacao
from app.models.arquivo_importado import ArquivoImportado
from datetime import datetime

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

st.title("Upload SPED")
st.divider()

arquivo = st.file_uploader(
    "Selecione o arquivo EFD (.txt)",
    type=["txt"],
    help="Arquivo SPED Fiscal no formato .txt gerado pelo SPED"
)

if arquivo:
    conteudo = arquivo.read().decode("latin-1")

    with st.spinner("Lendo cabeçalho do arquivo..."):
        try:
            metadados = processar_renomeacao(conteudo, arquivo.name)

            st.success("Arquivo lido com sucesso!")

            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Empresa:** {metadados['razao_social']}")
                st.info(f"**CNPJ:** {metadados['cnpj']}")
                st.info(f"**UF:** {metadados['uf']}")
            with col2:
                st.info(f"**Período:** {metadados['periodo_ini']} a {metadados['periodo_fin']}")
                st.info(f"**Nome original:** {metadados['nome_original']}")
                st.info(f"**Nome padronizado:** {metadados['novo_nome']}")

            st.divider()

            if st.button("Confirmar e processar", type="primary", use_container_width=True):
                with st.spinner("Salvando arquivo..."):

                    # salva o arquivo renomeado na pasta storage
                    caminho = os.path.join("storage", "arquivos", metadados['novo_nome'])
                    with open(caminho, "w", encoding="latin-1") as f:
                        f.write(conteudo)

                    # registra no banco
                    db = next(get_session())
                    registro = ArquivoImportado(
                        tenant_id=st.session_state.tenant_id,
                        nome_original=metadados['nome_original'],
                        nome_padronizado=metadados['novo_nome'],
                        cnpj=metadados['cnpj'],
                        periodo_ini=metadados['periodo_ini'],
                        periodo_fin=metadados['periodo_fin'],
                        status="pendente"
                    )
                    db.add(registro)
                    db.commit()

                    st.success(f"Arquivo salvo como **{metadados['novo_nome']}**")
                    st.info("Processamento bronze/silver será iniciado na próxima etapa.")

        except ValueError as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")
        except Exception as e:
            st.error(f"Erro inesperado: {str(e)}")