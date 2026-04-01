import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.repositories.fiscal_repo import FiscalRepository, _parse_aliq
from app.utils.theme import AZUL, VERDE, VERMELHO, AMBAR, COLOR_SEQ

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

tenant_id = st.session_state.tenant_id

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

MESES_LABEL = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Marco", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
}

CST_ICMS_DESCR = {
    "000": "Tributado integralmente",
    "010": "Tributado c/ cobranca de ST",
    "020": "Tributado c/ reducao de base",
    "030": "Isento/nao tributado c/ ST",
    "040": "Isento de ICMS",
    "041": "Nao tributado",
    "050": "Suspensao do ICMS",
    "051": "Diferimento",
    "060": "ICMS ja pago por ST",
    "070": "Reducao de base c/ ST",
    "090": "Outras situacoes",
    "103": "Isento (Simples Nacional)",
    "140": "Isento c/ reducao (SN)",
    "160": "ICMS cobrado por ST (SN)",
    "200": "Tributado pelo SN c/ credito",
    "201": "Tributado pelo SN c/ credito e ST",
    "260": "ICMS ST (Simples Nacional)",
    "460": "Isento (SN s/ credito)",
    "500": "ICMS ST recolhido anteriormente",
    "560": "Isento/NT ST (SN s/ credito)",
}

CST_ICMS_RESUMO = {
    "000": "Voce paga ICMS normal sobre essas vendas",
    "020": "ICMS com desconto na base de calculo — voce paga menos",
    "040": "Produto isento — sem ICMS nessas vendas",
    "041": "Nao tributado — sem ICMS",
    "060": "ICMS ja foi pago pelo fabricante/distribuidor (ST) — voce nao paga de novo na venda",
    "090": "Situacao especial — verificar caso a caso",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
    font=dict(size=12),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
)


def formatar_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor: float) -> str:
    return f"{valor:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_mes(yyyymm: str) -> str:
    return f"{MESES_LABEL.get(yyyymm[4:6], yyyymm[4:6])}/{yyyymm[:4]}"


def formatar_mes_curto(yyyymm: str) -> str:
    return f"{yyyymm[4:6]}/{yyyymm[:4]}"


# ---------------------------------------------------------------------------
# Dados iniciais e filtros
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = FiscalRepository(db, tenant_id)
    meses_raw = repo.meses_disponiveis()
    csts_raw = repo.csts_disponiveis()
    cfops_raw = repo.cfops_disponiveis()
finally:
    db.close()

st.title("Gestão Fiscal")
st.divider()

MESES_ABREV = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

anos_raw = sorted({m[:4] for m in meses_raw}, reverse=True)
meses_num_raw = sorted({m[4:] for m in meses_raw})

col_ano, col_mes, col_cst, col_cfop = st.columns(4)

sel_ano = col_ano.selectbox("Ano", ["Todos"] + anos_raw)
sel_meses = col_mes.multiselect(
    "Mês",
    options=meses_num_raw,
    format_func=lambda m: MESES_ABREV.get(m, m),
    placeholder="Todos",
)

ano_filtro = None if sel_ano == "Todos" else sel_ano
meses_filtro = sel_meses if sel_meses else None

sel_cst = col_cst.multiselect(
    "CST ICMS",
    options=csts_raw,
    format_func=lambda c: f"{c} - {CST_ICMS_DESCR.get(c, 'Outros')[:40]}",
)

sel_cfop = col_cfop.multiselect("CFOP", options=cfops_raw)

filtros = dict(ano=ano_filtro, meses=meses_filtro, cst_icms=sel_cst or None, cfop=sel_cfop or None)

# ---------------------------------------------------------------------------
# Metricas globais com delta
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = FiscalRepository(db, tenant_id)
    metricas = repo.metricas_visao_geral(**filtros)

    delta_icms = None
    delta_aliq = None
    delta_st = None
    delta_pis_cof = None
    delta_fat = None

    if ano_filtro and meses_filtro and len(meses_filtro) == 1 and len(meses_raw) > 1:
        yyyymm = ano_filtro + meses_filtro[0]
        idx = meses_raw.index(yyyymm) if yyyymm in meses_raw else -1
        if idx >= 0 and idx + 1 < len(meses_raw):
            mes_ant = meses_raw[idx + 1]
            ano_ant, mes_num_ant = mes_ant[:4], mes_ant[4:]
            f_ant = dict(ano=ano_ant, meses=[mes_num_ant], cst_icms=sel_cst or None, cfop=sel_cfop or None)
            m_ant = repo.metricas_visao_geral(**f_ant)
            delta_icms = metricas["icms_a_pagar"] - m_ant["icms_a_pagar"]
            delta_aliq = metricas["aliquota_efetiva"] - m_ant["aliquota_efetiva"]
            delta_st = metricas["pct_st"] - m_ant["pct_st"]
            delta_pis_cof = (metricas["total_pis"] + metricas["total_cofins"]) - (m_ant["total_pis"] + m_ant["total_cofins"])
            delta_fat = metricas["faturamento_total"] - m_ant["faturamento_total"]
finally:
    db.close()

st.divider()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "ICMS a Pagar",
    formatar_br(metricas["icms_a_pagar"]),
    delta=f"{formatar_br(delta_icms)} vs anterior" if delta_icms is not None else None,
    delta_color="inverse",
    help="Debito (saidas) menos credito (entradas). Valor positivo = imposto a recolher",
)
c2.metric(
    "Aliquota Efetiva",
    formatar_pct(metricas["aliquota_efetiva"]),
    delta=f"{delta_aliq:+.1f} pp vs anterior" if delta_aliq is not None else None,
    delta_color="inverse",
    help="ICMS debito / faturamento tributado (exclui ST e isento)",
)
c3.metric(
    "% Faturamento em ST",
    formatar_pct(metricas["pct_st"]),
    delta=f"{delta_st:+.1f} pp vs anterior" if delta_st is not None else None,
    help="Percentual do faturamento com ICMS ja pago por Substituicao Tributaria",
)
c4.metric(
    "PIS + COFINS (Saida)",
    formatar_br(metricas["total_pis"] + metricas["total_cofins"]),
    delta=f"{formatar_br(delta_pis_cof)} vs anterior" if delta_pis_cof is not None else None,
    delta_color="inverse",
    help="Total de PIS e COFINS nas saidas",
)
c5.metric(
    "Faturamento Total",
    formatar_br(metricas["faturamento_total"]),
    delta=f"{formatar_br(delta_fat)} vs anterior" if delta_fat is not None else None,
    help="Soma do valor das operacoes de saida (vl_opr no C190)",
)

# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

st.divider()

aba_geral, aba_icms, aba_st, aba_pis, aba_diag = st.tabs([
    "Visao Geral",
    "ICMS",
    "Substituicao Tributaria",
    "PIS/COFINS",
    "Diagnostico Fiscal",
])

# ===========================================================================
# ABA 1 — VISAO GERAL
# ===========================================================================

with aba_geral:

    db = next(get_session())
    try:
        repo = FiscalRepository(db, tenant_id)
        evolucao = repo.evolucao_mensal_tributos(**filtros)
        composicao = repo.composicao_tributaria(**filtros)
    finally:
        db.close()

    # --- Evolucao Mensal ---
    if evolucao:
        st.subheader("Evolucao Mensal de Tributos")

        df_evo = pd.DataFrame(evolucao)
        df_evo["mes_label"] = df_evo["mes"].apply(formatar_mes_curto)
        df_evo["icms_a_pagar"] = (df_evo["icms_debito"] - df_evo["icms_credito"]).clip(lower=0)

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(
            x=df_evo["mes_label"], y=df_evo["icms_debito"],
            name="ICMS Debito (Saida)", marker_color=VERMELHO,
            text=[formatar_br(v) for v in df_evo["icms_debito"]],
            textposition="outside", textfont=dict(size=9),
        ))
        fig_evo.add_trace(go.Bar(
            x=df_evo["mes_label"], y=df_evo["icms_credito"],
            name="ICMS Credito (Entrada)", marker_color=VERDE,
            text=[formatar_br(v) for v in df_evo["icms_credito"]],
            textposition="outside", textfont=dict(size=9),
        ))
        fig_evo.add_trace(go.Scatter(
            x=df_evo["mes_label"], y=df_evo["icms_a_pagar"],
            name="ICMS a Pagar", mode="lines+markers",
            line=dict(color=AZUL, width=3), marker=dict(size=8),
        ))
        fig_evo.update_layout(
            **PLOTLY_LAYOUT, barmode="group", height=420,
            yaxis=dict(title="Valor (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
        )
        st.plotly_chart(fig_evo, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

    # --- Composicao Tributaria ---
    col_comp1, col_comp2 = st.columns(2)

    with col_comp1:
        st.subheader("Composicao Tributaria das Saidas")
        comp_filtrado = {k: v for k, v in composicao.items() if v > 0}
        if comp_filtrado:
            df_comp = pd.DataFrame([
                {"Tributo": k, "Valor (R$)": v} for k, v in comp_filtrado.items()
            ])
            cores_comp = {
                "ICMS Proprio": AZUL,
                "ICMS-ST": VERMELHO,
                "PIS": VERDE,
                "COFINS": COLOR_SEQ[4],
            }
            fig_comp = px.pie(
                df_comp, values="Valor (R$)", names="Tributo",
                hole=0.45, color="Tributo", color_discrete_map=cores_comp,
            )
            fig_comp.update_layout(**PLOTLY_LAYOUT, height=350)
            fig_comp.update_traces(textposition="inside", textinfo="percent+label", textfont=dict(size=11))
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("Sem dados de tributos para o periodo.")

    with col_comp2:
        st.subheader("Resumo dos Tributos")
        st.markdown(f"""
| Tributo | Valor |
|---------|-------|
| ICMS Debito (Saida) | {formatar_br(metricas['icms_debito'])} |
| ICMS Credito (Entrada) | {formatar_br(metricas['icms_credito'])} |
| **ICMS a Pagar** | **{formatar_br(metricas['icms_a_pagar'])}** |
| PIS (Saida) | {formatar_br(metricas['total_pis'])} |
| COFINS (Saida) | {formatar_br(metricas['total_cofins'])} |
| **Total Tributos** | **{formatar_br(metricas['icms_a_pagar'] + metricas['total_pis'] + metricas['total_cofins'])}** |
        """)

# ===========================================================================
# ABA 2 — ICMS
# ===========================================================================

with aba_icms:

    db = next(get_session())
    try:
        repo = FiscalRepository(db, tenant_id)
        dist_cst = repo.distribuicao_por_cst(**filtros)
        analise_aliq = repo.analise_por_aliquota(**filtros)
        detalhe = repo.detalhe_c190(**filtros)
    finally:
        db.close()

    # --- Distribuicao por CST ---
    if dist_cst:
        st.subheader("Distribuicao por CST ICMS (Saidas)")

        grand_total_cst = sum(r.vl_opr or 0 for r in dist_cst)

        col_cst_chart, col_cst_table = st.columns([1, 1])

        with col_cst_chart:
            df_cst = pd.DataFrame([{
                "CST": r.cst_icms or "N/I",
                "Valor Operacoes (R$)": r.vl_opr or 0.0,
            } for r in dist_cst])
            df_cst = df_cst.sort_values("Valor Operacoes (R$)", ascending=True)

            fig_cst = px.bar(
                df_cst, x="Valor Operacoes (R$)", y="CST",
                orientation="h", color="Valor Operacoes (R$)",
                color_continuous_scale="Blues",
            )
            fig_cst.update_layout(**PLOTLY_LAYOUT, height=max(300, len(df_cst) * 35), showlegend=False, coloraxis_showscale=False)
            fig_cst.update_traces(
                text=[formatar_br(v) for v in df_cst["Valor Operacoes (R$)"]],
                textposition="auto", textfont=dict(size=10),
            )
            st.plotly_chart(fig_cst, use_container_width=True)

        with col_cst_table:
            rows_cst = []
            for r in dist_cst:
                cst = r.cst_icms or "N/I"
                vl = r.vl_opr or 0.0
                rows_cst.append({
                    "CST": cst,
                    "Descricao": CST_ICMS_DESCR.get(cst, "Outros"),
                    "Valor (R$)": vl,
                    "ICMS (R$)": r.vl_icms or 0.0,
                    "% do Total": (vl / grand_total_cst * 100) if grand_total_cst else 0.0,
                    "O que significa": CST_ICMS_RESUMO.get(cst, "—"),
                })
            df_cst_tab = pd.DataFrame(rows_cst)
            st.dataframe(
                df_cst_tab,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "% do Total": st.column_config.NumberColumn(format="%.1f %%"),
                },
            )
    else:
        st.info("Sem dados de CST para os filtros selecionados.")

    # --- Analise por Aliquota ---
    st.divider()
    if analise_aliq:
        st.subheader("Analise por Aliquota (excl. ST e Isento)")

        df_aliq = pd.DataFrame([{
            "Aliquota": f"{_parse_aliq(r.aliq_icms):.1f}%",
            "Aliq Num": _parse_aliq(r.aliq_icms),
            "Valor Operacoes (R$)": r.vl_opr or 0.0,
            "Base ICMS (R$)": r.vl_bc_icms or 0.0,
            "ICMS (R$)": r.vl_icms or 0.0,
            "Aliq Efetiva": ((r.vl_icms or 0) / (r.vl_opr or 1) * 100),
            "Registros": r.qtd,
        } for r in analise_aliq]).sort_values("Aliq Num", ascending=False)

        col_aliq_chart, col_aliq_table = st.columns([1, 1])

        with col_aliq_chart:
            fig_aliq = go.Figure()
            fig_aliq.add_trace(go.Bar(
                x=df_aliq["Aliquota"], y=df_aliq["Valor Operacoes (R$)"],
                name="Valor Operacoes", marker_color=AZUL,
                text=[formatar_br(v) for v in df_aliq["Valor Operacoes (R$)"]],
                textposition="outside", textfont=dict(size=9),
            ))
            fig_aliq.add_trace(go.Bar(
                x=df_aliq["Aliquota"], y=df_aliq["ICMS (R$)"],
                name="ICMS", marker_color=VERMELHO,
                text=[formatar_br(v) for v in df_aliq["ICMS (R$)"]],
                textposition="outside", textfont=dict(size=9),
            ))
            fig_aliq.update_layout(**PLOTLY_LAYOUT, barmode="group", height=350,
                yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)"))
            st.plotly_chart(fig_aliq, use_container_width=True)

        with col_aliq_table:
            st.dataframe(
                df_aliq.drop(columns=["Aliq Num"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor Operacoes (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Base ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Aliq Efetiva": st.column_config.NumberColumn(format="%.2f %%"),
                },
            )
    else:
        st.info("Sem dados de aliquota para os filtros selecionados.")

    # --- Tabela detalhada C190 ---
    st.divider()
    with st.expander("Tabela Detalhada C190"):
        if detalhe:
            df_det = pd.DataFrame([{
                "Data": dt_doc.strftime("%d/%m/%Y") if dt_doc else "-",
                "Num Doc": num_doc or "-",
                "Tipo": "Saida" if ind_oper == "1" else "Entrada",
                "Participante": nome_part or "-",
                "CST": c190.cst_icms or "-",
                "CFOP": c190.cfop or "-",
                "Aliquota": c190.aliq_icms or "-",
                "Vl Operacao (R$)": c190.vl_opr or 0.0,
                "BC ICMS (R$)": c190.vl_bc_icms or 0.0,
                "ICMS (R$)": c190.vl_icms or 0.0,
                "BC ST (R$)": c190.vl_bc_icms_st or 0.0,
                "ICMS ST (R$)": c190.vl_icms_st or 0.0,
            } for c190, dt_doc, num_doc, ind_oper, nome_part in detalhe])
            st.dataframe(
                df_det,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Vl Operacao (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "BC ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "BC ST (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "ICMS ST (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                },
            )
            st.caption(f"{len(detalhe)} registro(s) (limite 500)")
        else:
            st.info("Sem registros C190.")

# ===========================================================================
# ABA 3 — SUBSTITUICAO TRIBUTARIA
# ===========================================================================

with aba_st:

    db = next(get_session())
    try:
        repo = FiscalRepository(db, tenant_id)
        m_st = repo.metricas_st(ano=ano_filtro, meses=meses_filtro)
        top_st = repo.top_produtos_st_entrada(ano=ano_filtro, meses=meses_filtro, limit=20)
        evo_st = repo.evolucao_st_vs_proprio(ano=ano_filtro, meses=meses_filtro)
    finally:
        db.close()

    # --- Cards ST ---
    cs1, cs2, cs3 = st.columns(3)
    cs1.metric(
        "Total em Operacoes ST",
        formatar_br(m_st["total_st_saida"]),
        help="Valor das operacoes de saida com CST 060 (ICMS ja pago pelo fabricante)",
    )
    cs2.metric(
        "% do Faturamento em ST",
        formatar_pct(m_st["pct_st"]),
        help="Quanto do seu faturamento ja tem ICMS pago por substituicao tributaria",
    )
    cs3.metric(
        "ICMS-ST Pago nas Compras",
        formatar_br(m_st["icms_st_compras"]),
        help="Total de ICMS-ST destacado nas notas de entrada (vl_icms_st)",
    )

    st.divider()

    # --- Top produtos ST ---
    if top_st:
        st.subheader("Top Produtos com Maior Valor de Compra com ST")
        st.caption("Produtos comprados com CFOP 1403/2403 (comercializacao com substituicao tributaria)")

        df_st = pd.DataFrame([{
            "Produto": (r.descr_item or r.cod_item or "-")[:40],
            "Valor Total (R$)": r.vl_total or 0.0,
        } for r in top_st])
        df_st = df_st.sort_values("Valor Total (R$)", ascending=True)

        fig_st = px.bar(
            df_st, x="Valor Total (R$)", y="Produto",
            orientation="h", color="Valor Total (R$)",
            color_continuous_scale="Reds",
        )
        fig_st.update_layout(**PLOTLY_LAYOUT, height=max(350, len(df_st) * 28), showlegend=False, coloraxis_showscale=False)
        fig_st.update_traces(
            text=[formatar_br(v) for v in df_st["Valor Total (R$)"]],
            textposition="auto", textfont=dict(size=10),
        )
        st.plotly_chart(fig_st, use_container_width=True)

        # Tabela completa
        with st.expander("Ver tabela detalhada"):
            df_st_tab = pd.DataFrame([{
                "Codigo": r.cod_item or "-",
                "Descricao": r.descr_item or "-",
                "Valor Total (R$)": r.vl_total or 0.0,
                "ICMS (R$)": r.vl_icms or 0.0,
                "Qtd Itens": r.qtd_itens,
            } for r in top_st])
            st.dataframe(df_st_tab, use_container_width=True, hide_index=True,
                column_config={
                    "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                })
    else:
        st.info("Nenhum produto com CFOP de ST encontrado nas compras.")

    # --- Evolucao ST vs Proprio ---
    st.divider()
    if evo_st:
        st.subheader("Evolucao: ST vs ICMS Proprio (Saidas)")
        st.caption("Comparacao mensal do valor das operacoes com ST (CST 060) versus tributacao propria (CST 000/020)")

        df_evo_st = pd.DataFrame([{
            "Mes": formatar_mes_curto(r.mes),
            "Operacoes ST (R$)": r.vl_st or 0.0,
            "Operacoes ICMS Proprio (R$)": r.vl_proprio or 0.0,
        } for r in evo_st])

        fig_evo_st = go.Figure()
        fig_evo_st.add_trace(go.Scatter(
            x=df_evo_st["Mes"], y=df_evo_st["Operacoes ST (R$)"],
            name="ST (CST 060)", mode="lines+markers",
            line=dict(color=VERMELHO, width=3), marker=dict(size=8),
        ))
        fig_evo_st.add_trace(go.Scatter(
            x=df_evo_st["Mes"], y=df_evo_st["Operacoes ICMS Proprio (R$)"],
            name="ICMS Proprio (CST 000/020)", mode="lines+markers",
            line=dict(color=AZUL, width=3), marker=dict(size=8),
        ))
        fig_evo_st.update_layout(**PLOTLY_LAYOUT, height=380,
            yaxis=dict(title="Valor (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"))
        st.plotly_chart(fig_evo_st, use_container_width=True)
    else:
        st.info("Sem dados de evolucao ST para o periodo.")

# ===========================================================================
# ABA 4 — PIS/COFINS
# ===========================================================================

with aba_pis:

    db = next(get_session())
    try:
        repo = FiscalRepository(db, tenant_id)
        m_pis = repo.metricas_pis_cofins(ano=ano_filtro, meses=meses_filtro)
        evo_pis = repo.evolucao_pis_cofins(ano=ano_filtro, meses=meses_filtro)
    finally:
        db.close()

    # --- Cards ---
    cp1, cp2, cp3, cp4 = st.columns(4)
    cp1.metric("PIS Entrada", formatar_br(m_pis["pis_entrada"]),
               help="PIS destacado nas notas de compra")
    cp2.metric("COFINS Entrada", formatar_br(m_pis["cofins_entrada"]),
               help="COFINS destacado nas notas de compra")
    cp3.metric("PIS Saida", formatar_br(m_pis["pis_saida"]),
               help="PIS nas notas de venda")
    cp4.metric("COFINS Saida", formatar_br(m_pis["cofins_saida"]),
               help="COFINS nas notas de venda")

    st.divider()

    # --- Indicador monofasico ---
    total_entrada = m_pis["pis_entrada"] + m_pis["cofins_entrada"]
    total_saida = m_pis["pis_saida"] + m_pis["cofins_saida"]

    if total_entrada > 0 and total_saida < total_entrada * 0.3:
        pct_mono = (1 - total_saida / total_entrada) * 100 if total_entrada > 0 else 0
        st.success(
            f"**Regime Monofasico detectado** — Aproximadamente {pct_mono:.0f}% dos seus produtos "
            f"operam em regime monofasico.\n\n"
            f"Isso significa que o PIS/COFINS ja foi recolhido pelo fabricante/importador na "
            f"primeira etapa da cadeia. Voce **nao precisa pagar novamente** na revenda desses itens.\n\n"
            f"PIS+COFINS na entrada: **{formatar_br(total_entrada)}** | "
            f"PIS+COFINS na saida: **{formatar_br(total_saida)}**"
        )
    elif total_entrada > 0:
        st.info(
            f"PIS+COFINS na entrada: {formatar_br(total_entrada)} | "
            f"PIS+COFINS na saida: {formatar_br(total_saida)}"
        )

    # --- Evolucao PIS/COFINS ---
    if evo_pis:
        st.subheader("Evolucao Mensal PIS/COFINS")

        df_pis = pd.DataFrame(evo_pis)
        df_pis["mes_label"] = df_pis["mes"].apply(formatar_mes_curto)

        fig_pis = go.Figure()
        fig_pis.add_trace(go.Bar(
            x=df_pis["mes_label"], y=df_pis["pis_entrada"],
            name="PIS Entrada", marker_color=VERDE,
        ))
        fig_pis.add_trace(go.Bar(
            x=df_pis["mes_label"], y=df_pis["cofins_entrada"],
            name="COFINS Entrada", marker_color=COLOR_SEQ[4],
        ))
        fig_pis.add_trace(go.Bar(
            x=df_pis["mes_label"], y=df_pis["pis_saida"],
            name="PIS Saida", marker_color=AMBAR,
        ))
        fig_pis.add_trace(go.Bar(
            x=df_pis["mes_label"], y=df_pis["cofins_saida"],
            name="COFINS Saida", marker_color=VERMELHO,
        ))
        fig_pis.update_layout(**PLOTLY_LAYOUT, barmode="group", height=400,
            yaxis=dict(title="Valor (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"))
        st.plotly_chart(fig_pis, use_container_width=True)
    else:
        st.info("Sem dados de PIS/COFINS para o periodo.")

# ===========================================================================
# ABA 5 — DIAGNOSTICO FISCAL
# ===========================================================================

with aba_diag:

    db = next(get_session())
    try:
        repo = FiscalRepository(db, tenant_id)
        alertas = repo.alertas_cst_inconsistente(ano=ano_filtro, meses=meses_filtro)
        sem_cst = repo.produtos_sem_cst(ano=ano_filtro, meses=meses_filtro)
        concentracao = repo.concentracao_tributaria(ano=ano_filtro, meses=meses_filtro, limit=20)
    finally:
        db.close()

    # --- Alertas de inconsistencia ---
    st.subheader("Alertas de Inconsistencia")

    if alertas:
        st.warning(
            f"**{len(alertas)} produto(s)** com possivel erro de classificacao fiscal.\n\n"
            "Esses itens foram comprados com CFOP de Substituicao Tributaria (1403/2403), "
            "mas estao com CST 000 (tributado integralmente). "
            "Isso pode indicar que o CST deveria ser 060 (ST ja pago)."
        )
        df_alertas = pd.DataFrame([{
            "Codigo": r.cod_item or "-",
            "Descricao": r.descr_item or "-",
            "CST": r.cst_icms,
            "CFOP": r.cfop,
            "Ocorrencias": r.qtd,
            "Valor Total (R$)": r.vl_total or 0.0,
        } for r in alertas])
        st.dataframe(df_alertas, use_container_width=True, hide_index=True,
            column_config={
                "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            })
    else:
        st.success("Nenhuma inconsistencia de CST x CFOP encontrada.")

    st.divider()

    # --- Produtos sem CST ---
    st.subheader("Produtos sem Classificacao Fiscal")

    if sem_cst:
        st.warning(
            f"**{len(sem_cst)} produto(s)** sem CST ICMS definido nas notas de entrada."
        )
        df_sem = pd.DataFrame([{
            "Codigo": r.cod_item or "-",
            "Descricao": r.descr_item or "-",
            "Ocorrencias": r.qtd,
            "Valor Total (R$)": r.vl_total or 0.0,
        } for r in sem_cst])
        st.dataframe(df_sem, use_container_width=True, hide_index=True,
            column_config={
                "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            })
    else:
        st.success("Todos os produtos possuem CST definido.")

    st.divider()

    # --- Concentracao tributaria ---
    if concentracao:
        st.subheader("Concentracao Tributaria nas Compras")
        st.caption("Top 20 produtos com maior carga tributaria total (ICMS + PIS + COFINS) nas entradas")

        df_conc = pd.DataFrame([{
            "Produto": (r.descr_item or r.cod_item or "-")[:40],
            "Carga Total (R$)": r.carga_total or 0.0,
        } for r in concentracao])
        df_conc = df_conc.sort_values("Carga Total (R$)", ascending=True)

        fig_conc = px.bar(
            df_conc, x="Carga Total (R$)", y="Produto",
            orientation="h", color="Carga Total (R$)",
            color_continuous_scale="Oranges",
        )
        fig_conc.update_layout(**PLOTLY_LAYOUT, height=max(350, len(df_conc) * 28), showlegend=False, coloraxis_showscale=False)
        fig_conc.update_traces(
            text=[formatar_br(v) for v in df_conc["Carga Total (R$)"]],
            textposition="auto", textfont=dict(size=10),
        )
        st.plotly_chart(fig_conc, use_container_width=True)

        # Tabela detalhada
        with st.expander("Ver detalhamento"):
            df_conc_tab = pd.DataFrame([{
                "Codigo": r.cod_item or "-",
                "Descricao": r.descr_item or "-",
                "ICMS (R$)": r.vl_icms or 0.0,
                "PIS (R$)": r.vl_pis or 0.0,
                "COFINS (R$)": r.vl_cofins or 0.0,
                "Carga Total (R$)": r.carga_total or 0.0,
                "Valor Comprado (R$)": r.vl_item_total or 0.0,
                "% Carga": ((r.carga_total or 0) / (r.vl_item_total or 1) * 100),
            } for r in concentracao])
            st.dataframe(df_conc_tab, use_container_width=True, hide_index=True,
                column_config={
                    "ICMS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "PIS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "COFINS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Carga Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Valor Comprado (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "% Carga": st.column_config.NumberColumn(format="%.1f %%"),
                })
    else:
        st.info("Sem dados de concentracao tributaria.")
