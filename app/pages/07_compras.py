import streamlit as st
import pandas as pd
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.utils.formatters import formatar_cnpj
from app.repositories.compras_repo import ComprasRepository

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

tenant_id = st.session_state.tenant_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MESES_LABEL = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
}

COD_SIT = {
    "00": "Regular",
    "01": "Irregular",
    "02": "Cancelada",
    "03": "Cancelada por substituição",
    "04": "Denegada",
    "05": "Não numerada",
    "06": "Complementar",
    "07": "Extemporânea",
    "08": "Regime especial",
}


def formatar_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_qtd(valor: float) -> str:
    return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_mes(yyyymm: str) -> str:
    ano = yyyymm[:4]
    mes = yyyymm[4:6]
    return f"{MESES_LABEL.get(mes, mes)}/{ano}"


# ---------------------------------------------------------------------------
# Métricas globais e meses disponíveis
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    metricas = repo.metricas_globais()
    meses_raw = repo.meses_disponiveis()
finally:
    db.close()

st.title("Gestão de Compras")
st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Notas de entrada",
    f"{metricas['total_notas']:,}".replace(",", "."),
    help="Total de NF-e de entrada (C100, ind_oper=0)",
)
col2.metric(
    "Fornecedores",
    f"{metricas['total_fornecedores']:,}".replace(",", "."),
    help="Fornecedores distintos pelo cod_part",
)
col3.metric(
    "Valor total comprado",
    formatar_br(metricas["valor_total_compras"]),
    help="Soma do vl_doc de todas as notas de entrada",
)
col4.metric(
    "Itens comprados",
    f"{metricas['total_itens_comprados']:,}".replace(",", "."),
    help="Total de linhas C170 de notas de entrada",
)

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

st.divider()

col_mes, col_forn, col_nota, col_prod = st.columns(4)

opcoes_mes = ["Todos os meses"] + [formatar_mes(m) for m in meses_raw]
sel_mes = col_mes.selectbox("Período", opcoes_mes)

mes_map = {formatar_mes(m): m for m in meses_raw}
mes_selecionado = mes_map.get(sel_mes)  # None se "Todos os meses"

busca_forn = col_forn.text_input("Fornecedor", placeholder="CNPJ ou parte do nome")
busca_nota = col_nota.text_input("Nº da Nota", placeholder="Ex: 000123456")
busca_prod = col_prod.text_input("Produto", placeholder="Código ou descrição")

busca_forn = busca_forn.strip() or None
busca_nota = busca_nota.strip() or None
busca_prod = busca_prod.strip() or None

# ---------------------------------------------------------------------------
# Seção 1: Notas de Entrada
# ---------------------------------------------------------------------------

st.subheader("Notas de Entrada")

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    notas = repo.listar_notas(mes=mes_selecionado, fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)
finally:
    db.close()

if not notas:
    st.info("Nenhuma nota de entrada encontrada para os filtros selecionados.")
else:
    df_notas = pd.DataFrame([{
        "Data": doc.dt_doc.strftime("%d/%m/%Y") if doc.dt_doc else "—",
        "Nº Doc": doc.num_doc or "—",
        "Série": doc.ser or "—",
        "Fornecedor (CNPJ)": formatar_cnpj(doc.cod_part) if doc.cod_part else "—",
        "Situação": COD_SIT.get(doc.cod_sit, doc.cod_sit or "—"),
        "Vlr. Doc (R$)": doc.vl_doc or 0.0,
        "Vlr. Merc (R$)": doc.vl_merc or 0.0,
        "Desconto (R$)": doc.vl_desc or 0.0,
        "ICMS (R$)": doc.vl_icms or 0.0,
        "PIS (R$)": doc.vl_pis or 0.0,
        "COFINS (R$)": doc.vl_cofins or 0.0,
        "Chave NF-e": doc.chv_nfe or "—",
    } for doc in notas])

    st.dataframe(
        df_notas,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Vlr. Doc (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Vlr. Merc (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Desconto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "PIS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "COFINS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )
    total_notas_val = sum(d.vl_doc or 0.0 for d in notas)
    st.caption(f"{len(notas)} nota(s) | Total: {formatar_br(total_notas_val)}")

# ---------------------------------------------------------------------------
# Seção 2: Itens Comprados
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Itens Comprados")

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    itens_rows = repo.listar_itens(mes=mes_selecionado, fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)
finally:
    db.close()

if not itens_rows:
    st.info("Nenhum item encontrado para os filtros selecionados.")
else:
    df_itens = pd.DataFrame([{
        "Data NF": doc.dt_doc.strftime("%d/%m/%Y") if doc.dt_doc else "—",
        "Nº Doc": doc.num_doc or "—",
        "Fornecedor (CNPJ)": formatar_cnpj(doc.cod_part) if doc.cod_part else "—",
        "Nº Item": item.num_item,
        "Código": item.cod_item or "—",
        "Descrição": (produto.descr_item if produto else None) or item.descr_compl or "—",
        "Qtd": item.qtd or 0.0,
        "Unid": item.unid or (produto.unid_inv if produto else None) or "—",
        "Vlr. Item (R$)": item.vl_item or 0.0,
        "Desconto (R$)": item.vl_desc or 0.0,
        "CFOP": item.cfop or "—",
        "CST ICMS": item.cst_icms or "—",
        "Alíq. ICMS (%)": item.aliq_icms or 0.0,
        "ICMS (R$)": item.vl_icms or 0.0,
    } for item, doc, produto in itens_rows])

    st.dataframe(
        df_itens,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qtd": st.column_config.NumberColumn(format="%.3f"),
            "Vlr. Item (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Desconto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Alíq. ICMS (%)": st.column_config.NumberColumn(format="%.2f"),
            "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )
    total_itens_val = sum(i.vl_item or 0.0 for i, _, _ in itens_rows)
    st.caption(f"{len(itens_rows)} item(ns) | Total: {formatar_br(total_itens_val)}")

# ---------------------------------------------------------------------------
# Seção 3: Análise por Fornecedor
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Análise por Fornecedor")

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    por_fornecedor = repo.agrupar_por_fornecedor(mes=mes_selecionado, fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)
finally:
    db.close()

if not por_fornecedor:
    st.info("Nenhum fornecedor encontrado para o período selecionado.")
else:
    grand_total_forn = sum(r.total_compras or 0.0 for r in por_fornecedor)

    df_forn = pd.DataFrame([{
        "Fornecedor (CNPJ)": formatar_cnpj(r.cod_part) if r.cod_part else "Não informado",
        "Qtd. Notas": r.qtd_notas,
        "Total Compras (R$)": r.total_compras or 0.0,
        "Total ICMS (R$)": r.total_icms or 0.0,
        "Total PIS (R$)": r.total_pis or 0.0,
        "Total COFINS (R$)": r.total_cofins or 0.0,
        "% do Total": (r.total_compras or 0.0) / grand_total_forn * 100 if grand_total_forn else 0.0,
    } for r in por_fornecedor])

    st.dataframe(
        df_forn,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total Compras (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Total ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Total PIS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Total COFINS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "% do Total": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )
    st.caption(f"{len(por_fornecedor)} fornecedor(es)")

# ---------------------------------------------------------------------------
# Seção 4: Análise por Produto
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Análise por Produto")

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    por_produto = repo.agrupar_por_produto(mes=mes_selecionado, fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)
finally:
    db.close()

if not por_produto:
    st.info("Nenhum produto encontrado para os filtros selecionados.")
else:
    grand_total_prod = sum(r.vl_total or 0.0 for r in por_produto)

    df_prod = pd.DataFrame([{
        "Código": r.cod_item or "—",
        "Descrição": r.descr_item or "—",
        "Unidade": r.unid_inv or "—",
        "Qtd. Total": r.qtd_total or 0.0,
        "Vlr. Total (R$)": r.vl_total or 0.0,
        "Preço Médio (R$)": r.preco_medio or 0.0,
        "Nº Notas": r.qtd_notas,
        "% do Total": (r.vl_total or 0.0) / grand_total_prod * 100 if grand_total_prod else 0.0,
    } for r in por_produto])

    st.dataframe(
        df_prod,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qtd. Total": st.column_config.NumberColumn(format="%.3f"),
            "Vlr. Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Preço Médio (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "% do Total": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )
    st.caption(f"{len(por_produto)} produto(s) distintos")
