import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from app.components.sidebar import render_sidebar
from app.repositories.vendas_repo import VendasRepository, DIA_SEMANA_MAP
from app.utils.db import get_session
from app.utils.formatters import formatar_cnpj
from app.utils.theme import AZUL, VERDE, VERMELHO, AMBAR, COLOR_SEQ

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

st.set_page_config(page_title="Gestão de Vendas", layout="wide")
render_sidebar()

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------

PLOTLY_LAYOUT = dict(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

CFOP_SAIDA_GRUPO = {
    "5101": "Venda Varejo Normal",
    "5102": "Venda Varejo Normal",
    "5103": "Venda Varejo Normal",
    "5104": "Venda Varejo Normal",
    "5401": "Venda Varejo ST",
    "5402": "Venda Varejo ST",
    "5403": "Venda Varejo ST",
    "5405": "Venda Varejo ST",
    "5409": "Transf. Varejo ST",
    "5411": "Devolução Compra",
    "5412": "Devolução Compra",
    "5152": "Transferência Interna",
    "5153": "Transferência Interna",
    "5201": "Devolução Venda",
    "5202": "Devolução Venda",
    "5910": "Remessa",
    "5949": "Outras Saídas",
    "6101": "Venda Interestadual",
    "6102": "Venda Interestadual",
    "6403": "Venda Interestadual ST",
    "6405": "Venda Interestadual ST",
}

DIA_SEMANA_LABEL = {
    "0": "Dom", "1": "Seg", "2": "Ter",
    "3": "Qua", "4": "Qui", "5": "Sex", "6": "Sáb",
}

ORDEM_DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

MESES_NOME = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

CORES_ANO = COLOR_SEQ

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def fmt_mes(m):
    return f"{MESES_NOME.get(m[4:6], m[4:6])}/{m[0:4]}"

def fmt_mes_curto(m):
    return f"{MESES_NOME.get(m[4:6], m[4:6])}/{m[2:4]}"

def fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_brl_int(v):
    return f"R$ {v:,.0f}".replace(",", ".")

# ------------------------------------------------------------------
# Carrega meses disponíveis
# ------------------------------------------------------------------

tenant_id = st.session_state.tenant_id
db = next(get_session())
try:
    repo = VendasRepository(db, tenant_id)
    meses = repo.meses_disponiveis()
finally:
    db.close()

# ------------------------------------------------------------------
# Filtros
# ------------------------------------------------------------------

st.title("Gestão de Vendas")

anos_raw = sorted({m[:4] for m in meses}, reverse=True)
meses_num_raw = sorted({m[4:] for m in meses})
col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
with col_f1:
    sel_ano = st.selectbox("Ano", ["Todos"] + anos_raw)
    ano_filtro = None if sel_ano == "Todos" else sel_ano
with col_f2:
    sel_meses = st.multiselect(
        "Mês",
        options=meses_num_raw,
        format_func=lambda m: MESES_NOME.get(m, m),
        placeholder="Todos os meses",
    )
    meses_filtro = sel_meses if sel_meses else None
with col_f3:
    dias_sel = st.multiselect(
        "Dia da semana",
        options=ORDEM_DIAS,
        default=[],
        placeholder="Todos os dias",
    )
    dias_filtro = dias_sel if dias_sel else None

# ------------------------------------------------------------------
# Carrega dados globais (usados nos cards e em múltiplas abas)
# ------------------------------------------------------------------

db = next(get_session())
try:
    repo = VendasRepository(db, tenant_id)
    metricas = repo.metricas_globais(ano_filtro, meses_filtro, dias_filtro)
    evolucao = repo.evolucao_mensal(dias_filtro)
    dia_semana_data = repo.faturamento_por_dia_semana(ano_filtro, meses_filtro, dias_filtro)
finally:
    db.close()

# ------------------------------------------------------------------
# Cards de métricas
# ------------------------------------------------------------------

st.divider()
c1, c2, c3, c4, c5 = st.columns(5)

fat = metricas["faturamento"]
notas = metricas["total_notas"]
ticket = metricas["ticket_medio"]
fat_por_dia = metricas["fat_por_dia"]
dias_com_vendas = metricas["dias_com_vendas"]

# Melhor dia da semana (por faturamento médio, não absoluto)
melhor_dia = "—"
if dia_semana_data:
    df_dia_cards = pd.DataFrame(dia_semana_data)
    if not df_dia_cards.empty:
        idx_melhor = df_dia_cards["faturamento"].idxmax()
        melhor_dia = DIA_SEMANA_LABEL.get(df_dia_cards.loc[idx_melhor, "dia_semana"], "—")

c1.metric(
    "Faturamento Total",
    fmt_brl(fat),
    delta=fmt_brl(metricas["delta_fat"]) if metricas["delta_fat"] is not None else None,
)
c2.metric(
    "Nº de Notas",
    f"{notas:,}".replace(",", "."),
    delta=f"{metricas['delta_notas']:+,}".replace(",", ".") if metricas["delta_notas"] is not None else None,
)
c3.metric(
    "Ticket Médio",
    fmt_brl(ticket),
    delta=fmt_brl(metricas["delta_ticket"]) if metricas["delta_ticket"] is not None else None,
)
c4.metric(
    "Faturamento Médio/Dia",
    fmt_brl(fat_por_dia),
    help=f"Calculado sobre {dias_com_vendas} dias com vendas no período.",
)
c5.metric(
    "Melhor Dia da Semana",
    melhor_dia,
    help="Dia com maior faturamento total no período selecionado.",
)

st.divider()

# ------------------------------------------------------------------
# Abas
# ------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Visão Geral", "Ritmo de Vendas", "Mix Comercial", "Clientes B2B", "Ano a Ano",
])

# ==================== ABA 1: VISÃO GERAL ====================
with tab1:
    if not evolucao:
        st.info("Sem dados de faturamento para exibir.")
    else:
        df_evol = pd.DataFrame(evolucao)
        df_evol["cresc_pct"] = df_evol["faturamento"].pct_change() * 100
        df_evol["label_mes"] = df_evol["mes"].apply(fmt_mes)

        cores = [
            VERDE if (c is None or c >= 0) else VERMELHO
            for c in df_evol["cresc_pct"]
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_evol["label_mes"],
            y=df_evol["faturamento"],
            name="Faturamento",
            marker_color=cores,
            text=[fmt_brl_int(v) for v in df_evol["faturamento"]],
            textposition="outside",
            yaxis="y1",
        ))
        fig.add_trace(go.Scatter(
            x=df_evol["label_mes"],
            y=df_evol["cresc_pct"],
            name="Crescimento %",
            mode="lines+markers",
            line=dict(color=AMBAR, width=2),
            yaxis="y2",
        ))
        fig.update_layout(
            title="Evolução Mensal de Faturamento",
            yaxis=dict(title="Faturamento (R$)"),
            yaxis2=dict(title="Crescimento (%)", overlaying="y", side="right", showgrid=False),
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

        fat_acumulado = df_evol["faturamento"].sum()
        meses_com_dados = len(df_evol)
        projecao_anual = (fat_acumulado / meses_com_dados * 12) if meses_com_dados else 0.0

        col_a, col_b = st.columns(2)
        with col_a:
            df_evol["acumulado"] = df_evol["faturamento"].cumsum()
            fig_acum = go.Figure()
            fig_acum.add_trace(go.Scatter(
                x=df_evol["label_mes"],
                y=df_evol["acumulado"],
                fill="tozeroy",
                mode="lines+markers",
                name="Acumulado",
                line=dict(color=AZUL),
            ))
            fig_acum.update_layout(
                title="Faturamento Acumulado",
                yaxis_title="R$",
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_acum, use_container_width=True)

        with col_b:
            st.metric("Faturamento acumulado", fmt_brl(fat_acumulado))
            st.metric(
                "Projeção anual",
                fmt_brl(projecao_anual),
                help=f"Baseada na média dos {meses_com_dados} meses com dados.",
            )
            if meses_com_dados < 12:
                st.caption(f"Dados disponíveis: {meses_com_dados}/12 meses.")

# ==================== ABA 2: RITMO DE VENDAS ====================
with tab2:
    db = next(get_session())
    try:
        repo = VendasRepository(db, tenant_id)
        heatmap_data = repo.heatmap_dia_mes()
        ticket_data = repo.distribuicao_ticket(ano_filtro, meses_filtro, dias_filtro)
    finally:
        db.close()

    col_h, col_b = st.columns([3, 2])

    with col_h:
        if not heatmap_data:
            st.info("Sem dados para o heatmap.")
        else:
            df_heat = pd.DataFrame(heatmap_data)
            df_heat["dia_label"] = df_heat["dia_semana"].map(DIA_SEMANA_LABEL)
            df_heat["mes_label"] = df_heat["mes"].apply(fmt_mes_curto)

            # Ordem cronológica dos meses (YYYYMM → label)
            meses_ordenados = (
                df_heat[["mes", "mes_label"]]
                .drop_duplicates()
                .sort_values("mes")["mes_label"]
                .tolist()
            )

            pivot = df_heat.pivot_table(
                index="dia_label", columns="mes_label", values="faturamento", aggfunc="sum"
            ).fillna(0)
            pivot = pivot.reindex(index=[d for d in ORDEM_DIAS if d in pivot.index])
            pivot = pivot.reindex(columns=[m for m in meses_ordenados if m in pivot.columns])

            fig_heat = px.imshow(
                pivot,
                color_continuous_scale="Blues",
                labels={"color": "Faturamento (R$)"},
                title="Heatmap: Faturamento por Dia × Mês",
                aspect="auto",
            )
            fig_heat.update_traces(
                hovertemplate="<b>%{y}</b> – %{x}<br>R$ %{z:,.0f}<extra></extra>"
            )
            fig_heat.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_heat, use_container_width=True)

    with col_b:
        if not dia_semana_data:
            st.info("Sem dados por dia da semana.")
        else:
            df_dia = pd.DataFrame(dia_semana_data)
            df_dia["dia_label"] = df_dia["dia_semana"].map(DIA_SEMANA_LABEL)
            df_dia["ordem"] = df_dia["dia_label"].map(
                {d: i for i, d in enumerate(ORDEM_DIAS)}
            )
            df_dia = df_dia.sort_values("ordem")

            fig_dia = go.Figure()
            fig_dia.add_trace(go.Bar(
                x=df_dia["dia_label"],
                y=df_dia["faturamento"],
                name="Faturamento",
                marker_color=AZUL,
            ))
            fig_dia.add_trace(go.Scatter(
                x=df_dia["dia_label"],
                y=df_dia["ticket_medio"],
                name="Ticket Médio",
                mode="lines+markers",
                line=dict(color=AMBAR, width=2),
                yaxis="y2",
            ))
            fig_dia.update_layout(
                title="Faturamento por Dia da Semana",
                yaxis=dict(title="Faturamento (R$)"),
                yaxis2=dict(title="Ticket Médio (R$)", overlaying="y", side="right", showgrid=False),
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_dia, use_container_width=True)

    # Distribuição de ticket
    st.subheader("Distribuição de Ticket")
    if ticket_data:
        total_notas_hist = sum(ticket_data.values())
        faixas = list(ticket_data.keys())
        contagens = list(ticket_data.values())
        pcts = [c / total_notas_hist * 100 if total_notas_hist else 0 for c in contagens]

        fig_hist = go.Figure(go.Bar(
            x=faixas,
            y=contagens,
            text=[f"{p:.2f}%" for p in pcts],
            textposition="outside",
            marker_color=COLOR_SEQ[4],
        ))
        fig_hist.update_layout(
            title="Notas por Faixa de Valor",
            yaxis_title="Nº de Notas",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

        faixa_dom = max(ticket_data, key=ticket_data.get)
        pct_dom = ticket_data[faixa_dom] / total_notas_hist * 100 if total_notas_hist else 0
        st.info(
            f"**{pct_dom:.2f}% das vendas estão na faixa {faixa_dom}.** "
            "Isso reflete o perfil de compras rápidas e de baixo valor típico do varejo alimentar."
        )

# ==================== ABA 3: MIX COMERCIAL ====================
with tab3:
    db = next(get_session())
    try:
        repo = VendasRepository(db, tenant_id)
        cfop_data = repo.distribuicao_cfop(ano_filtro, meses_filtro, dias_filtro)
        cfop_evol = repo.evolucao_cfop_mensal(cfops_top=3)
    finally:
        db.close()

    if cfop_data:
        grupos: dict = {}
        for r in cfop_data:
            grupo = CFOP_SAIDA_GRUPO.get(r.cfop, "Outros") if r.cfop else "Outros"
            grupos[grupo] = grupos.get(grupo, 0.0) + (r.vl_opr or 0.0)

        df_cfop_g = pd.DataFrame([
            {"Grupo": k, "Valor (R$)": v} for k, v in grupos.items()
        ]).sort_values("Valor (R$)", ascending=True)

        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            fig_cfop = go.Figure(go.Bar(
                x=df_cfop_g["Valor (R$)"],
                y=df_cfop_g["Grupo"],
                orientation="h",
                marker_color=AZUL,
                text=[fmt_brl_int(v) for v in df_cfop_g["Valor (R$)"]],
                textposition="outside",
            ))
            fig_cfop.update_layout(
                title="Faturamento por Grupo de CFOP",
                xaxis_title="Valor (R$)",
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_cfop, use_container_width=True)

        with col_g2:
            total_cfop = sum(grupos.values())
            st.markdown("**Participação por grupo**")
            for grupo, valor in sorted(grupos.items(), key=lambda x: x[1], reverse=True):
                pct = valor / total_cfop * 100 if total_cfop else 0
                st.write(f"**{grupo}**: {pct:.2f}%")

        with st.expander("Ver CFOPs individuais"):
            df_ind = pd.DataFrame([
                {
                    "CFOP": r.cfop,
                    "Descrição": CFOP_SAIDA_GRUPO.get(r.cfop, "Outros"),
                    "Valor (R$)": r.vl_opr or 0.0,
                    "Qtd Registros": r.qtd or 0,
                }
                for r in cfop_data
            ])
            st.dataframe(df_ind, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de CFOP para o período selecionado.")

    if cfop_evol:
        st.subheader("Evolução Mensal por Principal CFOP")
        df_cfop_ev = pd.DataFrame(cfop_evol)
        df_cfop_ev["mes_label"] = df_cfop_ev["mes"].apply(fmt_mes)
        df_cfop_ev["cfop_label"] = df_cfop_ev["cfop"].map(
            lambda c: f"{c} – {CFOP_SAIDA_GRUPO.get(c, 'Outros')}"
        )

        fig_ev = px.line(
            df_cfop_ev,
            x="mes_label",
            y="vl_opr",
            color="cfop_label",
            markers=True,
            labels={"vl_opr": "Valor (R$)", "mes_label": "Mês", "cfop_label": "CFOP"},
            title="Top 3 CFOPs — Evolução Mensal",
        )
        fig_ev.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig_ev, use_container_width=True)

# ==================== ABA 4: CLIENTES B2B ====================
with tab4:
    db = next(get_session())
    try:
        repo = VendasRepository(db, tenant_id)
        clientes = repo.ranking_clientes(ano_filtro, meses_filtro, dias_filtro)
        top_clientes_evol = repo.evolucao_top_clientes(limit=5)
    finally:
        db.close()

    total_notas_geral = metricas["total_notas"]
    total_b2b_notas = sum(c["qtd_notas"] for c in clientes)
    pct_b2b = total_b2b_notas / total_notas_geral * 100 if total_notas_geral else 0

    if not clientes:
        st.info("Nenhum cliente B2B identificado no período. Todas as vendas são para consumidor final.")
    else:
        st.caption(
            f"**{len(clientes)} clientes B2B identificados.** "
            f"Representam {pct_b2b:.2f}% das notas. "
            "Clientes com CNPJ registrado na nota fiscal."
        )

        df_cli = pd.DataFrame(clientes)
        df_cli_bar = df_cli.sort_values("fat_total", ascending=True).tail(15)

        fig_cli = go.Figure(go.Bar(
            x=df_cli_bar["fat_total"],
            y=df_cli_bar["nome_part"],
            orientation="h",
            marker_color=COLOR_SEQ[4],
            text=[fmt_brl_int(v) for v in df_cli_bar["fat_total"]],
            textposition="outside",
        ))
        fig_cli.update_layout(
            title="Ranking de Clientes B2B por Faturamento",
            xaxis_title="Faturamento (R$)",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_cli, use_container_width=True)

        if top_clientes_evol:
            df_ev_cli = pd.DataFrame(top_clientes_evol)
            df_ev_cli["mes_label"] = df_ev_cli["mes"].apply(fmt_mes)

            fig_ev_cli = px.line(
                df_ev_cli,
                x="mes_label",
                y="fat_total",
                color="nome_part",
                markers=True,
                labels={"fat_total": "Faturamento (R$)", "mes_label": "Mês", "nome_part": "Cliente"},
                title="Top 5 Clientes B2B — Evolução Mensal",
            )
            fig_ev_cli.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_ev_cli, use_container_width=True)

        st.subheader("Detalhamento por Cliente")
        df_tab = pd.DataFrame([
            {
                "Cliente": c["nome_part"],
                "CNPJ": formatar_cnpj(c["cnpj_part"]) if c["cnpj_part"] != "—" else "—",
                "Faturamento Total": fmt_brl(c["fat_total"]),
                "Nº Notas": c["qtd_notas"],
                "Ticket Médio": fmt_brl(c["ticket_medio"]),
                "Última Nota": c["ultima_nota"].strftime("%d/%m/%Y") if c["ultima_nota"] else "—",
            }
            for c in clientes
        ])
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

# ==================== ABA 5: ANO A ANO ====================
with tab5:
    if not evolucao:
        st.info("Sem dados suficientes para comparativo anual.")
    else:
        df_yoy = pd.DataFrame(evolucao)
        df_yoy["ano"] = df_yoy["mes"].str[:4]
        df_yoy["mes_num"] = df_yoy["mes"].str[4:]
        df_yoy["mes_label"] = df_yoy["mes_num"].map(MESES_NOME)

        anos = sorted(df_yoy["ano"].unique())

        if len(anos) < 2:
            st.info(
                "Comparativo disponível apenas com dados de 2 anos ou mais. "
                f"Atualmente há dados apenas de {anos[0] if anos else '—'}."
            )
        else:
            # Gráfico de barras agrupadas por mês
            fig_yoy = go.Figure()
            for i, ano in enumerate(anos):
                df_ano = df_yoy[df_yoy["ano"] == ano].sort_values("mes_num")
                fig_yoy.add_trace(go.Bar(
                    x=df_ano["mes_label"],
                    y=df_ano["faturamento"],
                    name=ano,
                    marker_color=CORES_ANO[i % len(CORES_ANO)],
                    text=[fmt_brl_int(v) for v in df_ano["faturamento"]],
                    textposition="outside",
                ))
            fig_yoy.update_layout(
                title="Comparativo de Faturamento Mensal por Ano",
                barmode="group",
                yaxis_title="Faturamento (R$)",
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_yoy, use_container_width=True)

            # Tabela de variação ano a ano por mês
            pivot = df_yoy.pivot_table(
                index="mes_num", columns="ano", values="faturamento", aggfunc="sum"
            ).fillna(0)

            rows_comp = []
            for mes_num in sorted(pivot.index):
                row = {"Mês": MESES_NOME.get(mes_num, mes_num)}
                for j, ano in enumerate(anos):
                    v = pivot.loc[mes_num, ano] if ano in pivot.columns else 0.0
                    row[ano] = fmt_brl_int(v)
                for j in range(1, len(anos)):
                    ano_ant = anos[j - 1]
                    ano_atu = anos[j]
                    v_ant = pivot.loc[mes_num, ano_ant] if ano_ant in pivot.columns else 0.0
                    v_atu = pivot.loc[mes_num, ano_atu] if ano_atu in pivot.columns else 0.0
                    if v_ant > 0:
                        row[f"Δ {ano_ant}→{ano_atu}"] = f"{(v_atu - v_ant) / v_ant * 100:+.2f}%"
                    elif v_atu > 0:
                        row[f"Δ {ano_ant}→{ano_atu}"] = "Novo"
                    else:
                        row[f"Δ {ano_ant}→{ano_atu}"] = "—"
                rows_comp.append(row)

            st.subheader("Variação Mês a Mês por Ano")
            st.dataframe(pd.DataFrame(rows_comp), use_container_width=True, hide_index=True)

            # Totais anuais
            st.subheader("Totais por Ano")
            col_totais = st.columns(len(anos))
            for i, ano in enumerate(anos):
                total_ano = df_yoy[df_yoy["ano"] == ano]["faturamento"].sum()
                delta_ano = None
                if i > 0:
                    ano_ant = anos[i - 1]
                    total_ant = df_yoy[df_yoy["ano"] == ano_ant]["faturamento"].sum()
                    if total_ant > 0:
                        delta_pct = (total_ano - total_ant) / total_ant * 100
                        delta_ano = f"{delta_pct:+.2f}%"
                col_totais[i].metric(f"Total {ano}", fmt_brl(total_ano), delta=delta_ano)
