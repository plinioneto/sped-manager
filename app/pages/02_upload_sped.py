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

arquivos = st.file_uploader(
    "Selecione os arquivos EFD (.txt)",
    type=["txt"],
    accept_multiple_files=True,
    help="Arquivos SPED Fiscal no formato .txt gerado pelo SPED"
)

if arquivos:
    st.subheader(f"{len(arquivos)} arquivo(s) selecionado(s)")
    st.divider()

    # pré-visualiza os metadados de cada arquivo
    metadados_lista = []
    erro = False

    for arquivo in arquivos:
        conteudo = arquivo.read().decode("latin-1")
        try:
            metadados = processar_renomeacao(conteudo, arquivo.name)
            metadados['conteudo'] = conteudo
            metadados_lista.append(metadados)

            with st.expander(f"{metadados['razao_social']} — {metadados['periodo_ini']} a {metadados['periodo_fin']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Empresa:** {metadados['razao_social']}")
                    st.info(f"**CNPJ:** {metadados['cnpj']}")
                    st.info(f"**UF:** {metadados['uf']}")
                with col2:
                    st.info(f"**Período:** {metadados['periodo_ini']} a {metadados['periodo_fin']}")
                    st.info(f"**Nome original:** {metadados['nome_original']}")
                    st.info(f"**Nome padronizado:** {metadados['novo_nome']}")

        except ValueError as e:
            st.error(f"Erro em {arquivo.name}: {str(e)}")
            erro = True

    st.divider()

    if not erro:
        if st.button("Confirmar e processar todos", type="primary", use_container_width=True):

            db = next(get_session())
            resultados = []

            for metadados in metadados_lista:
                with st.spinner(f"Processando {metadados['novo_nome']}..."):
                    bronze = BronzeProcessor(db, st.session_state.tenant_id)

                    if bronze.arquivo_ja_ingerido(metadados['novo_nome']):
                        resultados.append({
                            "arquivo": metadados['novo_nome'],
                            "status": "ignorado",
                            "linhas": 0
                        })
                        continue

                    # salva arquivo renomeado
                    caminho = os.path.join("storage", "arquivos", metadados['novo_nome'])
                    with open(caminho, "w", encoding="latin-1") as f:
                        f.write(metadados['conteudo'])

                    # registra no banco
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

                    # camada bronze
                    try:
                        resultado_bronze = bronze.ingerir(metadados['conteudo'], metadados['novo_nome'])
                        registro.status = "bronze_concluido"
                        registro.processado_em = datetime.utcnow()
                        db.commit()
                        resultados.append({
                            "arquivo": metadados['novo_nome'],
                            "status": "concluido",
                            "linhas": resultado_bronze['linhas']
                        })
                    except Exception as e:
                        registro.status = "erro"
                        registro.erro_msg = str(e)
                        db.commit()
                        resultados.append({
                            "arquivo": metadados['novo_nome'],
                            "status": "erro",
                            "linhas": 0,
                            "erro": str(e)
                        })

            # exibe resumo final
            st.divider()
            st.subheader("Resumo da importação")

            for r in resultados:
                if r['status'] == "concluido":
                    st.success(f"{r['arquivo']} — {r['linhas']} linhas ingeridas")
                elif r['status'] == "ignorado":
                    st.warning(f"{r['arquivo']} — já importado anteriormente")
                else:
                    st.error(f"{r['arquivo']} — erro: {r.get('erro', '')}")