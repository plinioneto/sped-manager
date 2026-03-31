import os
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.produto import Produto
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.icms_c190 import IcmsC190
from app.models.arquivo_importado import ArquivoImportado
from app.models.efd_raw import EfdRaw
from app.parser.renomeador import processar_renomeacao
from app.parser.bronze import BronzeProcessor
from app.parser.silver import SilverProcessor

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

MESES = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
}

tenant_id = st.session_state.tenant_id
brt = timezone(timedelta(hours=-3))


def executar_delecao(arq_id: int):
    db = next(get_session())
    try:
        arq = db.query(ArquivoImportado).filter(
            ArquivoImportado.id == arq_id,
            ArquivoImportado.tenant_id == tenant_id,
        ).first()

        if not arq:
            return

        try:
            dt_ini = datetime.strptime(arq.periodo_ini, "%Y%m%d")
            dt_fin = datetime.strptime(arq.periodo_fin, "%Y%m%d")
        except Exception:
            dt_ini = dt_fin = None

        if dt_ini and dt_fin:
            doc_ids = [
                row.id for row in db.query(DocumentoFiscal.id).filter(
                    DocumentoFiscal.tenant_id == tenant_id,
                    DocumentoFiscal.dt_doc >= dt_ini,
                    DocumentoFiscal.dt_doc <= dt_fin,
                ).all()
            ]
            if doc_ids:
                db.query(IcmsC190).filter(
                    IcmsC190.documento_id.in_(doc_ids)
                ).delete(synchronize_session=False)
                db.query(ItemFiscal).filter(
                    ItemFiscal.documento_id.in_(doc_ids)
                ).delete(synchronize_session=False)
                db.query(DocumentoFiscal).filter(
                    DocumentoFiscal.id.in_(doc_ids)
                ).delete(synchronize_session=False)

        db.query(EfdRaw).filter(
            EfdRaw.tenant_id == tenant_id,
            EfdRaw.file_path == arq.nome_padronizado,
        ).delete(synchronize_session=False)

        caminho = os.path.join("storage", "arquivos", arq.nome_padronizado)
        if os.path.exists(caminho):
            os.remove(caminho)

        db.delete(arq)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@st.dialog("Confirmar exclusão")
def dialog_confirmar_delecao(arq):
    st.warning(
        f"Deseja apagar **{arq.nome_padronizado}**?\n\n"
        "Todos os dados importados desse arquivo (notas fiscais, itens, C190 e EFD bruto) serão removidos permanentemente."
    )
    c1, c2 = st.columns(2)
    if c1.button("Apagar", type="primary", use_container_width=True):
        executar_delecao(arq.id)
        del st.session_state["deletar_arquivo_id"]
        st.rerun()
    if c2.button("Cancelar", use_container_width=True):
        del st.session_state["deletar_arquivo_id"]
        st.rerun()


st.title("Dados")
st.divider()

tab_upload, tab_historico = st.tabs(["Upload", "Histórico"])

# ===========================================================================
# ABA: UPLOAD
# ===========================================================================

with tab_upload:
    arquivos = st.file_uploader(
        "Selecione os arquivos EFD (.txt)",
        type=["txt"],
        accept_multiple_files=True,
        help="Arquivos SPED Fiscal no formato .txt gerado pelo SPED"
    )

    if arquivos:
        st.subheader(f"{len(arquivos)} arquivo(s) selecionado(s)")
        st.divider()

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
                    bronze = BronzeProcessor(db, st.session_state.tenant_id)

                    if bronze.arquivo_ja_ingerido(metadados['novo_nome']):
                        resultados.append({
                            "arquivo": metadados['novo_nome'],
                            "status": "ignorado",
                            "linhas": 0
                        })
                        continue

                    # etapa 1 — salva arquivo renomeado
                    caminho = os.path.join("storage", "arquivos", metadados['novo_nome'])
                    with open(caminho, "w", encoding="latin-1") as f:
                        f.write(metadados['conteudo'])

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

                    # etapa 2 — bronze
                    with st.spinner(f"Bronze: {metadados['novo_nome']}..."):
                        try:
                            resultado_bronze = bronze.ingerir(
                                metadados['conteudo'],
                                metadados['novo_nome']
                            )
                            registro.status = "bronze_concluido"
                            db.commit()
                        except Exception as e:
                            registro.status = "erro"
                            registro.erro_msg = str(e)
                            db.commit()
                            resultados.append({
                                "arquivo": metadados['novo_nome'],
                                "status": "erro",
                                "erro": str(e)
                            })
                            continue

                    # etapa 3 — silver
                    with st.spinner(f"Silver: {metadados['novo_nome']}..."):
                        try:
                            silver = SilverProcessor(db, st.session_state.tenant_id)
                            resultado_silver = silver.processar(metadados['novo_nome'])

                            registro.status = "concluido"
                            registro.processado_em = datetime.utcnow()
                            db.commit()

                            resultados.append({
                                "arquivo": metadados['novo_nome'],
                                "status": "concluido",
                                "linhas_bronze": resultado_bronze['linhas'],
                                "documentos": resultado_silver['documentos'],
                                "itens": resultado_silver['itens'],
                                "produtos_criados": resultado_silver['produtos_criados'],
                                "produtos_atualizados": resultado_silver['produtos_atualizados'],
                            })
                        except Exception as e:
                            registro.status = "erro"
                            registro.erro_msg = str(e)
                            db.commit()
                            resultados.append({
                                "arquivo": metadados['novo_nome'],
                                "status": "erro",
                                "erro": str(e)
                            })

                # resumo final
                st.divider()
                st.subheader("Resumo da importação")

                for r in resultados:
                    if r['status'] == "concluido":
                        with st.expander(f"{r['arquivo']} — concluído", expanded=True):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric(
                                    label="Linhas brutas",
                                    value=r['linhas_bronze'],
                                    help="Total de linhas lidas do arquivo EFD"
                                )
                            with col2:
                                st.metric(
                                    label="Notas fiscais",
                                    value=r['documentos'],
                                    help="Quantidade de NFes únicas importadas (bloco C100)"
                                )
                            with col3:
                                st.metric(
                                    label="Itens de notas",
                                    value=r['itens'],
                                    help="Linhas de produtos dentro das notas fiscais (bloco C170)"
                                )
                            with col4:
                                st.metric(
                                    label="Produtos novos",
                                    value=r['produtos_criados'],
                                    help="Produtos cadastrados pela primeira vez (bloco 0200)"
                                )
                    elif r['status'] == "ignorado":
                        st.warning(f"{r['arquivo']} — já importado anteriormente")
                    else:
                        st.error(f"{r['arquivo']} — erro: {r.get('erro', '')}")

# ===========================================================================
# ABA: HISTÓRICO
# ===========================================================================

with tab_historico:
    db = next(get_session())

    total_notas = db.query(func.count(DocumentoFiscal.id)).filter(
        DocumentoFiscal.tenant_id == tenant_id
    ).scalar() or 0

    total_produtos = db.query(func.count(Produto.id)).filter(
        Produto.tenant_id == tenant_id
    ).scalar() or 0

    valor_total = db.query(func.sum(DocumentoFiscal.vl_doc)).filter(
        DocumentoFiscal.tenant_id == tenant_id
    ).scalar() or 0.0

    total_itens = db.query(func.count(ItemFiscal.id)).filter(
        ItemFiscal.tenant_id == tenant_id
    ).scalar() or 0

    ultima_data = db.query(func.max(DocumentoFiscal.dt_doc)).filter(
        DocumentoFiscal.tenant_id == tenant_id
    ).scalar()

    todos_arquivos = (
        db.query(ArquivoImportado)
        .filter(ArquivoImportado.tenant_id == tenant_id)
        .order_by(ArquivoImportado.criado_em.desc())
        .all()
    )

    metricas_por_arquivo = {}
    for arq in todos_arquivos:
        try:
            dt_ini = datetime.strptime(arq.periodo_ini, "%Y%m%d")
            dt_fin = datetime.strptime(arq.periodo_fin, "%Y%m%d")
        except Exception:
            dt_ini = dt_fin = None

        if dt_ini and dt_fin:
            notas = db.query(func.count(DocumentoFiscal.id)).filter(
                DocumentoFiscal.tenant_id == tenant_id,
                DocumentoFiscal.dt_doc >= dt_ini,
                DocumentoFiscal.dt_doc <= dt_fin,
            ).scalar() or 0
            valor = db.query(func.sum(DocumentoFiscal.vl_doc)).filter(
                DocumentoFiscal.tenant_id == tenant_id,
                DocumentoFiscal.dt_doc >= dt_ini,
                DocumentoFiscal.dt_doc <= dt_fin,
            ).scalar() or 0.0
        else:
            notas = 0
            valor = 0.0

        metricas_por_arquivo[arq.id] = {"notas": notas, "valor": valor}

    db.close()

    # --- alertas ---
    arquivos_problema = [a for a in todos_arquivos if a.status in ("erro", "pendente")]
    if arquivos_problema:
        st.subheader("Alertas")
        for arq in arquivos_problema:
            if arq.status == "erro":
                st.error(f"**{arq.nome_padronizado}** — {arq.erro_msg or 'Erro desconhecido'}")
            else:
                st.warning(f"**{arq.nome_padronizado}** — importação pendente")
        st.divider()

    # --- métricas globais ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Notas fiscais", f"{total_notas:,}".replace(",", "."), help="Total de documentos fiscais (C100)")
    col2.metric("Produtos cadastrados", f"{total_produtos:,}".replace(",", "."), help="Total de produtos no cadastro (0200)")
    col3.metric(
        "Valor total das notas",
        f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        help="Soma do vl_doc de todos os documentos fiscais"
    )
    col4.metric("Itens de NF", f"{total_itens:,}".replace(",", "."), help="Total de itens nas notas fiscais (C170)")
    col5.metric(
        "Última data na análise",
        ultima_data.strftime("%d/%m/%Y") if ultima_data else "—",
        help="Data mais recente entre os documentos fiscais importados"
    )

    st.divider()

    # --- tabela de arquivos ---
    st.subheader("Arquivos importados")

    if not todos_arquivos:
        st.info("Nenhum arquivo importado ainda.")
    else:
        meses_raw = sorted({
            arq.periodo_ini[:6]
            for arq in todos_arquivos
            if arq.periodo_ini and len(arq.periodo_ini) == 8
        }, reverse=True)

        def formatar_mes(yyyymm: str) -> str:
            return f"{MESES[yyyymm[4:6]]}/{yyyymm[:4]}"

        opcoes_mes = ["Todos os meses"] + [formatar_mes(m) for m in meses_raw]
        filtro = st.selectbox("Filtrar por mês", opcoes_mes, label_visibility="collapsed")

        if filtro != "Todos os meses":
            idx = opcoes_mes.index(filtro) - 1
            mes_selecionado = meses_raw[idx]
            arquivos_filtrados = [
                a for a in todos_arquivos
                if a.periodo_ini and a.periodo_ini[:6] == mes_selecionado
            ]
        else:
            arquivos_filtrados = todos_arquivos

        rows = []
        for arq in arquivos_filtrados:
            try:
                ini = datetime.strptime(arq.periodo_ini, "%Y%m%d").strftime("%d/%m/%Y")
                fin = datetime.strptime(arq.periodo_fin, "%Y%m%d").strftime("%d/%m/%Y")
                periodo = f"{ini} → {fin}"
            except Exception:
                periodo = "—"

            importado_em = (
                arq.criado_em.replace(tzinfo=timezone.utc).astimezone(brt).strftime("%d/%m/%Y %H:%M")
                if arq.criado_em else "—"
            )

            m = metricas_por_arquivo.get(arq.id, {"notas": 0, "valor": 0.0})

            if arq.status == "concluido":
                status = "✅ concluído"
            elif arq.status == "erro":
                status = "❌ erro"
            else:
                status = "⏳ pendente"

            rows.append({
                "_id": arq.id,
                "Arquivo": arq.nome_padronizado,
                "Período": periodo,
                "Notas fiscais": m["notas"],
                "Valor total (R$)": round(m["valor"], 2),
                "Importado em": importado_em,
                "Status": status,
            })

        df = pd.DataFrame(rows)

        st.caption("Clique em uma linha para selecioná-la e apagar o arquivo.")
        evento = st.dataframe(
            df.drop(columns=["_id"]),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        linhas_selecionadas = evento.selection.rows
        if linhas_selecionadas:
            arq_id = df.iloc[linhas_selecionadas[0]]["_id"]
            arq_alvo = next((a for a in arquivos_filtrados if a.id == arq_id), None)
            if arq_alvo:
                st.button(
                    f"🗑️ Apagar {arq_alvo.nome_padronizado}",
                    type="secondary",
                    on_click=lambda: st.session_state.update({"deletar_arquivo_id": arq_id}),
                )

    # --- modal de confirmação ---
    if "deletar_arquivo_id" in st.session_state:
        arq_id = st.session_state["deletar_arquivo_id"]
        arq_alvo = next((a for a in todos_arquivos if a.id == arq_id), None)
        if arq_alvo:
            dialog_confirmar_delecao(arq_alvo)
