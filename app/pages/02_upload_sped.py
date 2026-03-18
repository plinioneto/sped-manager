import streamlit as st
import os
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.parser.renomeador import processar_renomeacao
from app.parser.bronze import BronzeProcessor
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

                db = next(get_session())
                bronze = BronzeProcessor(db, st.session_state.tenant_id)

                if bronze.arquivo_ja_ingerido(metadados['novo_nome']):
                    st.warning("Este arquivo já foi importado anteriormente.")
                else:
                    with st.spinner("Salvando arquivo..."):
                        caminho = os.path.join("storage", "arquivos", metadados['novo_nome'])
                        with open(caminho, "w", encoding="latin-1") as f:
                            f.write(conteudo)

                    registro = ArquivoImportado(
                        tenant_id=st.session_state.tenant_id,
                        nome_original=metadados['nome_original'],
                        nome_padronizado=metadados['novo_nome'],
                        cnpj=metadados['cnpj'],
                        periodo_ini=metadados['periodo_ini'],
                        periodo_fin=metadados['periodo_fin'],
                        status="processando"
                    )
                    db.add(registro)
                    db.commit()

                    with st.spinner("Ingerindo camada bronze..."):
                        try:
                            resultado_bronze = bronze.ingerir(conteudo, metadados['novo_nome'])
                            registro.status = "bronze_concluido"
                            registro.processado_em = datetime.utcnow()
                            db.commit()
                            st.success(f"Bronze concluído! {resultado_bronze['linhas']} linhas ingeridas.")
                        except Exception as e:
                            registro.status = "erro"
                            registro.erro_msg = str(e)
                            db.commit()
                            st.error(f"Erro no bronze: {str(e)}")

        except ValueError as e:
            st.error(f"Erro ao ler o arquivo: {str(e)}")
        except Exception as e:
            st.error(f"Erro inesperado: {str(e)}")