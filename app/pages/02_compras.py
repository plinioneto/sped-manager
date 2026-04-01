import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.utils.formatters import formatar_cnpj
from app.repositories.compras_repo import ComprasRepository
from app.utils.theme import AZUL, VERDE, VERMELHO, AMBAR, COLOR_SEQ

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
    "00": "Regular", "01": "Irregular", "02": "Cancelada",
    "03": "Cancelada por substituição", "04": "Denegada",
    "05": "Não numerada", "06": "Complementar",
    "07": "Extemporânea", "08": "Regime especial",
}

CFOP_DESCR = {
    "1101": "Compra p/ industrialização",
    "1102": "Compra p/ comercialização",
    "1126": "Compra p/ utilização na prestação de serviço",
    "1152": "Transferência p/ comercialização",
    "1403": "Compra p/ comercialização c/ ST",
    "1406": "Compra de ativo imobilizado c/ ST",
    "1407": "Compra de uso e consumo c/ ST",
    "1409": "Transferência de mercadoria c/ ST",
    "1551": "Compra de ativo imobilizado",
    "1556": "Compra de material de uso e consumo",
    "1652": "Compra de energia elétrica",
    "1653": "Compra de energia elétrica p/ distribuição",
    "1910": "Entrada de bonificação/doação",
    "1949": "Outra entrada não especificada",
    "2102": "Compra p/ comercialização (interestadual)",
    "2403": "Compra p/ comercialização c/ ST (interestadual)",
    "2406": "Compra de ativo imobilizado c/ ST (interestadual)",
    "2407": "Compra de uso e consumo c/ ST (interestadual)",
    "2551": "Compra de ativo imobilizado (interestadual)",
    "2556": "Compra de uso e consumo (interestadual)",
    "2910": "Entrada de bonificação/doação (interestadual)",
}

CFOP_GRUPO = {
    "1102": "Mercadoria p/ Revenda",
    "1403": "Mercadoria p/ Revenda",
    "2102": "Mercadoria p/ Revenda",
    "2403": "Mercadoria p/ Revenda",
    "1152": "Transferências",
    "1409": "Transferências",
    "1101": "Industrialização",
    "1407": "Uso e Consumo",
    "1556": "Uso e Consumo",
    "2407": "Uso e Consumo",
    "2556": "Uso e Consumo",
    "1406": "Ativo Imobilizado",
    "1551": "Ativo Imobilizado",
    "2406": "Ativo Imobilizado",
    "2551": "Ativo Imobilizado",
    "1652": "Energia Elétrica",
    "1653": "Energia Elétrica",
    "1910": "Bonificação/Doação",
    "2910": "Bonificação/Doação",
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


def formatar_qtd(valor: float) -> str:
    return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_mes(yyyymm: str) -> str:
    ano = yyyymm[:4]
    mes = yyyymm[4:6]
    return f"{MESES_LABEL.get(mes, mes)}/{ano}"


def formatar_mes_curto(yyyymm: str) -> str:
    ano = yyyymm[:4]
    mes = yyyymm[4:6]
    return f"{mes}/{ano}"


def cnpj_curto(cnpj: str) -> str:
    """Retorna CNPJ formatado ou truncado para caber em gráficos."""
    if cnpj and len(cnpj) == 14:
        return formatar_cnpj(cnpj)
    return cnpj or "N/I"


def nome_fornecedor(row) -> str:
    """Retorna nome do participante ou CNPJ formatado como fallback."""
    nome = getattr(row, "nome_part", None)
    if nome:
        return nome
    cnpj = getattr(row, "cnpj_part", None)
    if cnpj and len(cnpj) == 14:
        return formatar_cnpj(cnpj)
    cod = getattr(row, "cod_part", None)
    return cnpj_curto(cod) if cod else "N/I"


# ---------------------------------------------------------------------------
# Dados iniciais e filtros
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    meses_raw = repo.meses_disponiveis()
finally:
    db.close()

st.title("Gestão de Compras")
st.divider()

# Filtros
MESES_ABREV = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

anos_raw = sorted({m[:4] for m in meses_raw}, reverse=True)
meses_num_raw = sorted({m[4:] for m in meses_raw})

col_ano, col_mes, col_forn, col_nota, col_prod = st.columns(5)

sel_ano = col_ano.selectbox("Ano", ["Todos"] + anos_raw)
sel_meses = col_mes.multiselect(
    "Mês",
    options=meses_num_raw,
    format_func=lambda m: MESES_ABREV.get(m, m),
    placeholder="Todos",
)

ano_filtro = None if sel_ano == "Todos" else sel_ano
meses_filtro = sel_meses if sel_meses else None

busca_forn = col_forn.text_input("Fornecedor", placeholder="CNPJ ou parte do nome")
busca_nota = col_nota.text_input("Nº da Nota", placeholder="Ex: 000123456")
busca_prod = col_prod.text_input("Produto", placeholder="Código ou descrição")

busca_forn = busca_forn.strip() or None
busca_nota = busca_nota.strip() or None
busca_prod = busca_prod.strip() or None

filtros = dict(ano=ano_filtro, meses=meses_filtro, fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)

# ---------------------------------------------------------------------------
# Métricas globais com delta
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)
    metricas = repo.metricas_globais(**filtros)

    # Calcula delta: métricas do mês anterior vs selecionado (só se filtrou por mês)
    delta_notas = None
    delta_forn = None
    delta_valor = None
    delta_itens = None

    if ano_filtro and meses_filtro and len(meses_filtro) == 1 and len(meses_raw) > 1:
        yyyymm = ano_filtro + meses_filtro[0]
        idx = meses_raw.index(yyyymm) if yyyymm in meses_raw else -1
        if idx >= 0 and idx + 1 < len(meses_raw):
            mes_ant = meses_raw[idx + 1]
            ano_ant, mes_num_ant = mes_ant[:4], mes_ant[4:]
            filtros_ant = dict(ano=ano_ant, meses=[mes_num_ant], fornecedor=busca_forn, num_nota=busca_nota, produto=busca_prod)
            metricas_ant = repo.metricas_globais(**filtros_ant)
            delta_notas = metricas["total_notas"] - metricas_ant["total_notas"]
            delta_forn = metricas["total_fornecedores"] - metricas_ant["total_fornecedores"]
            delta_valor = metricas["valor_total_compras"] - metricas_ant["valor_total_compras"]
            delta_itens = metricas["total_itens_comprados"] - metricas_ant["total_itens_comprados"]
finally:
    db.close()

st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Notas de entrada",
    f"{metricas['total_notas']:,}".replace(",", "."),
    delta=f"{delta_notas:+d} vs mês anterior" if delta_notas is not None else None,
    help="Total de NF-e de entrada (C100, ind_oper=0)",
)
col2.metric(
    "Fornecedores",
    f"{metricas['total_fornecedores']:,}".replace(",", "."),
    delta=f"{delta_forn:+d} vs mês anterior" if delta_forn is not None else None,
    help="Fornecedores distintos pelo cod_part",
)
col3.metric(
    "Valor total comprado",
    formatar_br(metricas["valor_total_compras"]),
    delta=f"{formatar_br(delta_valor)} vs mês anterior" if delta_valor is not None else None,
    help="Soma do vl_doc de todas as notas de entrada",
)
col4.metric(
    "Itens comprados",
    f"{metricas['total_itens_comprados']:,}".replace(",", "."),
    delta=f"{delta_itens:+d} vs mês anterior" if delta_itens is not None else None,
    help="Total de linhas C170 de notas de entrada",
)

# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

st.divider()

aba_geral, aba_forn, aba_prod, aba_notas = st.tabs([
    "Visão Geral",
    "Fornecedores",
    "Produtos",
    "Notas e Itens",
])

# ===========================================================================
# ABA 1 — VISÃO GERAL
# ===========================================================================

with aba_geral:

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        evolucao = repo.evolucao_mensal(**filtros)
        cfop_data = repo.distribuicao_cfop(**filtros)
        top_forn = repo.agrupar_por_fornecedor(**filtros)
    finally:
        db.close()

    # --- Evolução mensal ---
    if evolucao:
        st.subheader("Evolução Mensal de Compras")

        df_evo = pd.DataFrame([{
            "Mês": formatar_mes_curto(r.mes),
            "Valor Total (R$)": r.valor_total or 0.0,
            "Notas": r.total_notas or 0,
            "Ticket Médio (R$)": r.ticket_medio or 0.0,
        } for r in evolucao])

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(
            x=df_evo["Mês"],
            y=df_evo["Valor Total (R$)"],
            name="Valor Total",
            marker_color=AZUL,
            text=[formatar_br(v) for v in df_evo["Valor Total (R$)"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_evo.add_trace(go.Scatter(
            x=df_evo["Mês"],
            y=df_evo["Ticket Médio (R$)"],
            name="Ticket Médio",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=VERMELHO, width=2),
            marker=dict(size=6),
        ))
        fig_evo.update_layout(
            **PLOTLY_LAYOUT,
            yaxis=dict(title="Valor Total (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
            yaxis2=dict(title="Ticket Médio (R$)", overlaying="y", side="right", showgrid=False),
            height=380,
        )
        st.plotly_chart(fig_evo, use_container_width=True)
    else:
        st.info("Sem dados de evolução mensal para os filtros selecionados.")

    # --- Top 10 fornecedores + CFOP lado a lado ---
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Top 10 Fornecedores")
        if top_forn:
            top10 = top_forn[:10]
            df_top = pd.DataFrame([{
                "Fornecedor": nome_fornecedor(r),
                "Valor (R$)": r.total_compras or 0.0,
            } for r in top10])
            df_top = df_top.sort_values("Valor (R$)", ascending=True)

            fig_top = px.bar(
                df_top, x="Valor (R$)", y="Fornecedor",
                orientation="h",
                color="Valor (R$)",
                color_continuous_scale="Blues",
            )
            fig_top.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=False, coloraxis_showscale=False)
            fig_top.update_traces(
                text=[formatar_br(v) for v in df_top["Valor (R$)"]],
                textposition="auto",
                textfont=dict(size=10),
            )
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Nenhum fornecedor encontrado.")

    with col_chart2:
        st.subheader("Distribuição por Finalidade (CFOP)")
        if cfop_data:
            # Agrupa CFOPs por finalidade
            grupos = {}
            for r in cfop_data:
                grupo = CFOP_GRUPO.get(r.cfop, "Outros") if r.cfop else "Outros"
                if grupo not in grupos:
                    grupos[grupo] = {"Valor (R$)": 0.0, "Itens": 0}
                grupos[grupo]["Valor (R$)"] += r.valor_total or 0.0
                grupos[grupo]["Itens"] += r.qtd_itens or 0

            df_cfop = pd.DataFrame([
                {"Finalidade": g, "Valor (R$)": v["Valor (R$)"], "Itens": v["Itens"]}
                for g, v in grupos.items()
            ]).sort_values("Valor (R$)", ascending=False)

            cores_grupo = {
                "Mercadoria p/ Revenda": AZUL,
                "Transferências": COLOR_SEQ[5],
                "Industrialização": AMBAR,
                "Uso e Consumo": COLOR_SEQ[4],
                "Ativo Imobilizado": COLOR_SEQ[1],
                "Energia Elétrica": COLOR_SEQ[2],
                "Bonificação/Doação": VERMELHO,
                "Outros": "#97A0AF",
            }

            fig_cfop = px.pie(
                df_cfop, values="Valor (R$)", names="Finalidade",
                hole=0.45,
                color="Finalidade",
                color_discrete_map=cores_grupo,
            )
            fig_cfop.update_layout(**PLOTLY_LAYOUT, height=380)
            fig_cfop.update_traces(
                textposition="inside",
                textinfo="percent+label",
                textfont=dict(size=11),
            )
            st.plotly_chart(fig_cfop, use_container_width=True)

            # Detalhamento por CFOP individual em expander
            with st.expander("Ver detalhamento por CFOP"):
                df_detalhe = pd.DataFrame([{
                    "CFOP": r.cfop or "N/I",
                    "Descrição": CFOP_DESCR.get(r.cfop, "Outros") if r.cfop else "N/I",
                    "Finalidade": CFOP_GRUPO.get(r.cfop, "Outros") if r.cfop else "Outros",
                    "Valor (R$)": r.valor_total or 0.0,
                    "Itens": r.qtd_itens or 0,
                } for r in cfop_data])
                st.dataframe(
                    df_detalhe,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    },
                )
        else:
            st.info("Nenhum dado de CFOP encontrado.")


# ===========================================================================
# ABA 2 — FORNECEDORES
# ===========================================================================

with aba_forn:

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        por_fornecedor = repo.agrupar_por_fornecedor(**filtros)
        forn_evolucao = repo.top_fornecedores_evolucao(limit=5, **filtros)
    finally:
        db.close()

    if not por_fornecedor:
        st.info("Nenhum fornecedor encontrado para os filtros selecionados.")
    else:
        # --- Pareto de fornecedores ---
        st.subheader("Concentração de Fornecedores (Pareto)")

        grand_total = sum(r.total_compras or 0.0 for r in por_fornecedor)
        acumulado = 0.0
        pareto_data = []
        for r in por_fornecedor:
            val = r.total_compras or 0.0
            acumulado += val
            pareto_data.append({
                "Fornecedor": nome_fornecedor(r),
                "Valor (R$)": val,
                "% Acumulado": (acumulado / grand_total * 100) if grand_total else 0.0,
            })

        df_pareto = pd.DataFrame(pareto_data[:20])

        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(
            x=df_pareto["Fornecedor"],
            y=df_pareto["Valor (R$)"],
            name="Valor",
            marker_color=AZUL,
        ))
        fig_pareto.add_trace(go.Scatter(
            x=df_pareto["Fornecedor"],
            y=df_pareto["% Acumulado"],
            name="% Acumulado",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=VERMELHO, width=2),
            marker=dict(size=6),
        ))
        fig_pareto.add_hline(
            y=80, line_dash="dash", line_color="rgba(255,107,107,0.5)",
            annotation_text="80%", yref="y2",
        )
        fig_pareto.update_layout(
            **PLOTLY_LAYOUT,
            yaxis=dict(title="Valor (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
            yaxis2=dict(title="% Acumulado", overlaying="y", side="right", range=[0, 105]),
            height=400,
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig_pareto, use_container_width=True)

        # --- Evolução top 5 ---
        if forn_evolucao:
            st.subheader("Evolução Mensal — Top 5 Fornecedores")

            df_forn_evo = pd.DataFrame([{
                "Mês": formatar_mes_curto(r.mes),
                "Fornecedor": r.nome_part or cnpj_curto(r.cod_part),
                "Valor (R$)": r.valor_total or 0.0,
            } for r in forn_evolucao])

            fig_forn_evo = px.line(
                df_forn_evo, x="Mês", y="Valor (R$)", color="Fornecedor",
                markers=True,
            )
            fig_forn_evo.update_layout(**PLOTLY_LAYOUT, height=380)
            st.plotly_chart(fig_forn_evo, use_container_width=True)

        # --- Tabela de fornecedores ---
        st.subheader("Ranking de Fornecedores")

        df_forn = pd.DataFrame([{
            "Fornecedor": nome_fornecedor(r),
            "CNPJ": formatar_cnpj(r.cnpj_part) if r.cnpj_part and len(r.cnpj_part) == 14 else (r.cnpj_part or "—"),
            "Qtd. Notas": r.qtd_notas,
            "Total Compras (R$)": r.total_compras or 0.0,
            "Total ICMS (R$)": r.total_icms or 0.0,
            "Total PIS (R$)": r.total_pis or 0.0,
            "Total COFINS (R$)": r.total_cofins or 0.0,
            "% do Total": (r.total_compras or 0.0) / grand_total * 100 if grand_total else 0.0,
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


# ===========================================================================
# ABA 3 — PRODUTOS
# ===========================================================================

with aba_prod:

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        por_produto = repo.agrupar_por_produto(**filtros)
    finally:
        db.close()

    if not por_produto:
        st.info("Nenhum produto encontrado para os filtros selecionados.")
    else:
        grand_total_prod = sum(r.vl_total or 0.0 for r in por_produto)

        # --- Curva ABC ---
        st.subheader("Curva ABC de Produtos")

        acumulado = 0.0
        abc_data = []
        for r in por_produto:
            val = r.vl_total or 0.0
            acumulado += val
            pct_acum = (acumulado / grand_total_prod * 100) if grand_total_prod else 0.0
            if pct_acum <= 80:
                classe = "A"
            elif pct_acum <= 95:
                classe = "B"
            else:
                classe = "C"
            abc_data.append({
                "Produto": (r.descr_item or r.cod_item or "—")[:30],
                "Código": r.cod_item or "—",
                "Valor (R$)": val,
                "% Acumulado": pct_acum,
                "Classe": classe,
            })

        df_abc = pd.DataFrame(abc_data)
        total_a = len([x for x in abc_data if x["Classe"] == "A"])
        total_b = len([x for x in abc_data if x["Classe"] == "B"])
        total_c = len([x for x in abc_data if x["Classe"] == "C"])

        # Cards resumo ABC
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Classe A (80% do valor)", f"{total_a} produtos")
        col_b.metric("Classe B (80-95%)", f"{total_b} produtos")
        col_c.metric("Classe C (95-100%)", f"{total_c} produtos")

        # Gráfico top 20 com curva acumulada
        df_abc_top = df_abc.head(20)
        cores_abc = {"A": AZUL, "B": AMBAR, "C": "#BDBDBD"}

        fig_abc = go.Figure()
        for classe in ["A", "B", "C"]:
            mask = df_abc_top["Classe"] == classe
            if mask.any():
                fig_abc.add_trace(go.Bar(
                    x=df_abc_top.loc[mask, "Produto"],
                    y=df_abc_top.loc[mask, "Valor (R$)"],
                    name=f"Classe {classe}",
                    marker_color=cores_abc[classe],
                ))
        fig_abc.add_trace(go.Scatter(
            x=df_abc_top["Produto"],
            y=df_abc_top["% Acumulado"],
            name="% Acumulado",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=VERMELHO, width=2),
            marker=dict(size=5),
        ))
        fig_abc.add_hline(y=80, line_dash="dash", line_color="rgba(79,139,249,0.4)", annotation_text="80%", yref="y2")
        fig_abc.add_hline(y=95, line_dash="dash", line_color="rgba(255,167,38,0.4)", annotation_text="95%", yref="y2")
        fig_abc.update_layout(
            **PLOTLY_LAYOUT,
            barmode="stack",
            yaxis=dict(title="Valor (R$)", showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
            yaxis2=dict(title="% Acumulado", overlaying="y", side="right", range=[0, 105]),
            height=420,
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig_abc, use_container_width=True)

        # --- Top 20 produtos (barras horizontais) ---
        st.subheader("Top 20 Produtos por Valor de Compra")

        df_top_prod = pd.DataFrame([{
            "Produto": (r.descr_item or r.cod_item or "—")[:35],
            "Valor (R$)": r.vl_total or 0.0,
        } for r in por_produto[:20]])
        df_top_prod = df_top_prod.sort_values("Valor (R$)", ascending=True)

        fig_top_prod = px.bar(
            df_top_prod, x="Valor (R$)", y="Produto",
            orientation="h",
            color="Valor (R$)",
            color_continuous_scale="Blues",
        )
        fig_top_prod.update_layout(**PLOTLY_LAYOUT, height=max(350, len(df_top_prod) * 28), showlegend=False, coloraxis_showscale=False)
        fig_top_prod.update_traces(
            text=[formatar_br(v) for v in df_top_prod["Valor (R$)"]],
            textposition="auto",
            textfont=dict(size=10),
        )
        st.plotly_chart(fig_top_prod, use_container_width=True)

        # --- Tabela completa ---
        st.subheader("Detalhamento por Produto")

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


# ===========================================================================
# ABA 4 — NOTAS E ITENS
# ===========================================================================

with aba_notas:

    # --- Notas de Entrada ---
    st.subheader("Notas de Entrada")

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        notas = repo.listar_notas(**filtros)
    finally:
        db.close()

    if not notas:
        st.info("Nenhuma nota de entrada encontrada para os filtros selecionados.")
    else:
        df_notas = pd.DataFrame([{
            "Data": doc.dt_doc.strftime("%d/%m/%Y") if doc.dt_doc else "—",
            "Nº Doc": doc.num_doc or "—",
            "Série": doc.ser or "—",
            "Fornecedor": nome_part or cnpj_curto(doc.cod_part),
            "CNPJ Fornecedor": formatar_cnpj(doc.cod_part) if doc.cod_part else "—",
            "Situação": COD_SIT.get(doc.cod_sit, doc.cod_sit or "—"),
            "Vlr. Doc (R$)": doc.vl_doc or 0.0,
            "Vlr. Merc (R$)": doc.vl_merc or 0.0,
            "Desconto (R$)": doc.vl_desc or 0.0,
            "ICMS (R$)": doc.vl_icms or 0.0,
            "PIS (R$)": doc.vl_pis or 0.0,
            "COFINS (R$)": doc.vl_cofins or 0.0,
            "Chave NF-e": doc.chv_nfe or "—",
        } for doc, nome_part in notas])

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
        total_notas_val = sum(doc.vl_doc or 0.0 for doc, _ in notas)
        st.caption(f"{len(notas)} nota(s) | Total: {formatar_br(total_notas_val)}")

    # --- Itens Comprados ---
    st.divider()
    st.subheader("Itens Comprados")

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        itens_rows = repo.listar_itens(**filtros)
    finally:
        db.close()

    if not itens_rows:
        st.info("Nenhum item encontrado para os filtros selecionados.")
    else:
        df_itens = pd.DataFrame([{
            "Data NF": doc.dt_doc.strftime("%d/%m/%Y") if doc.dt_doc else "—",
            "Nº Doc": doc.num_doc or "—",
            "Fornecedor": nome_part or cnpj_curto(doc.cod_part),
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
        } for item, doc, produto, nome_part in itens_rows])

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
        total_itens_val = sum(i.vl_item or 0.0 for i, _, _, _ in itens_rows)
        st.caption(f"{len(itens_rows)} item(ns) | Total: {formatar_br(total_itens_val)}")
