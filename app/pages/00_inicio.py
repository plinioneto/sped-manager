import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import app.models

from app.components.sidebar import render_sidebar
from app.components.filtro_hierarquia import render_filtro_hierarquia
from app.repositories.vendas_repo import VendasRepository
from app.repositories.fiscal_repo import FiscalRepository
from app.repositories.compras_repo import ComprasRepository
from app.utils.db import get_session
from app.utils.theme import AZUL, VERDE, VERMELHO, AMBAR, COLOR_SEQ
from app.models.arquivo_importado import ArquivoImportado

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

st.set_page_config(page_title="Início", layout="wide")
render_sidebar()

tenant_id = st.session_state.tenant_id

# Filtro de hierarquia na sidebar
_db_hier = next(get_session())
try:
    filtro_h = render_filtro_hierarquia(_db_hier, key_prefix="inicio")
finally:
    _db_hier.close()

h_params = {
    "departamento_id": filtro_h["departamento_id"],
    "grupo_id": filtro_h["grupo_id"],
    "categoria_id": filtro_h["categoria_id"],
}

MESES_NOME = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

PLOTLY_LAYOUT = dict(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    margin=dict(l=10, r=10, t=40, b=10),
)


def fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_brl_int(v):
    return f"R$ {v:,.0f}".replace(",", ".")


def fmt_mes(m):
    return f"{MESES_NOME.get(m[4:6], m[4:6])}/{m[2:4]}"


# ------------------------------------------------------------------
# Carga de dados
# ------------------------------------------------------------------

db = next(get_session())
try:
    repo_v = VendasRepository(db, tenant_id)
    repo_f = FiscalRepository(db, tenant_id)
    repo_c = ComprasRepository(db, tenant_id)

    meses_v = repo_v.meses_disponiveis()
    meses_f = repo_f.meses_disponiveis()

    # Mês mais recente com dados de vendas
    mes_atual = meses_v[0] if meses_v else None
    mes_ant = meses_v[1] if len(meses_v) > 1 else None

    ano_atual = mes_atual[:4] if mes_atual else None
    mes_num_atual = mes_atual[4:] if mes_atual else None
    ano_ant = mes_ant[:4] if mes_ant else None
    mes_num_ant = mes_ant[4:] if mes_ant else None

    # Métricas de vendas — mês atual e anterior
    metricas_v = repo_v.metricas_globais(ano_atual, [mes_num_atual], **h_params) if mes_atual else {}
    metricas_v_ant = repo_v.metricas_globais(ano_ant, [mes_num_ant], **h_params) if mes_ant else {}

    # Métricas fiscais — mês atual
    metricas_f = repo_f.metricas_visao_geral(ano=ano_atual, meses=[mes_num_atual], **h_params) if mes_atual else {}

    # Evolução mensal de vendas (últimos 6 meses)
    evolucao = repo_v.evolucao_mensal(**h_params)
    evolucao_6 = evolucao[-6:] if len(evolucao) >= 6 else evolucao

    # Top 5 fornecedores do mês atual
    top_forn = repo_c.agrupar_por_fornecedor(ano=ano_atual, meses=[mes_num_atual], **h_params)
    top5_forn = top_forn[:5] if top_forn else []

    # Composição do faturamento por departamento (mês atual)
    composicao_depto = repo_v.composicao_por_departamento(ano=ano_atual, meses=[mes_num_atual]) if mes_atual else []

    # Último arquivo importado
    ultimo_arq = (
        db.query(ArquivoImportado)
        .filter(
            ArquivoImportado.tenant_id == tenant_id,
            ArquivoImportado.status == "ok",
        )
        .order_by(ArquivoImportado.processado_em.desc())
        .first()
    )
finally:
    db.close()

# ------------------------------------------------------------------
# Cabeçalho
# ------------------------------------------------------------------

periodo_label = (
    f"{MESES_NOME.get(mes_num_atual, mes_num_atual)}/{ano_atual}"
    if mes_atual else "—"
)

st.title("Início")

filtro_ativo = filtro_h["departamento_id"] or filtro_h["grupo_id"] or filtro_h["categoria_id"]
caption_parts = [f"Período de referência: **{periodo_label}** — dados do mês mais recente importado"]
if filtro_ativo:
    nomes = []
    if filtro_h["departamento_id"]:
        nomes.append(f"Depto: {st.session_state.get('inicio_depto', '')}")
    if filtro_h["grupo_id"]:
        nomes.append(f"Grupo: {st.session_state.get('inicio_grupo', '')}")
    if filtro_h["categoria_id"]:
        nomes.append(f"Cat: {st.session_state.get('inicio_cat', '')}")
    caption_parts.append(f"Filtro ativo: {' > '.join(nomes)}")
st.caption(" | ".join(caption_parts))
st.divider()

# ------------------------------------------------------------------
# Cards principais
# ------------------------------------------------------------------

fat = metricas_v.get("faturamento", 0.0)
fat_ant = metricas_v_ant.get("faturamento", 0.0)
delta_fat_pct = ((fat - fat_ant) / fat_ant * 100) if fat_ant else None

ticket = metricas_v.get("ticket_medio", 0.0)
ticket_ant = metricas_v_ant.get("ticket_medio", 0.0)

icms_pagar = metricas_f.get("icms_a_pagar", 0.0)
aliq_ef = metricas_f.get("aliquota_efetiva", 0.0)

total_pis_cof = metricas_f.get("total_pis", 0.0) + metricas_f.get("total_cofins", 0.0)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Faturamento do Mês",
    fmt_brl(fat),
    delta=f"{delta_fat_pct:+.1f}% vs mês anterior" if delta_fat_pct is not None else None,
)
c2.metric(
    "ICMS a Pagar",
    fmt_brl(icms_pagar),
    delta=f"Alíq. efetiva: {aliq_ef:.1f}%",
    delta_color="off",
    help="Débito de ICMS (saídas) menos crédito (entradas)",
)
c3.metric(
    "Ticket Médio",
    fmt_brl(ticket),
    delta=f"Mês anterior: {fmt_brl(ticket_ant)}" if mes_ant else None,
    delta_color="off",
)
c4.metric(
    "PIS + COFINS (Saída)",
    fmt_brl(total_pis_cof),
    help="Total de PIS e COFINS nas saídas do período",
)

st.divider()

# ------------------------------------------------------------------
# Gráficos
# ------------------------------------------------------------------

col_esq, col_dir = st.columns([3, 2])

# --- Evolução de faturamento (últimos 6 meses) ---
with col_esq:
    st.subheader("Faturamento — Últimos 6 Meses")
    if evolucao_6:
        df_ev = pd.DataFrame(evolucao_6)
        df_ev["cresc"] = df_ev["faturamento"].pct_change() * 100
        df_ev["label"] = df_ev["mes"].apply(fmt_mes)
        cores = [VERDE if (c is None or c >= 0) else VERMELHO for c in df_ev["cresc"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_ev["label"],
            y=df_ev["faturamento"],
            marker_color=cores,
            text=[fmt_brl_int(v) for v in df_ev["faturamento"]],
            textposition="outside",
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=df_ev["label"],
            y=df_ev["cresc"],
            name="Crescimento %",
            mode="lines+markers",
            line=dict(color=AMBAR, width=2),
            yaxis="y2",
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            yaxis=dict(title="Faturamento (R$)", showgrid=True),
            yaxis2=dict(title="Crescimento (%)", overlaying="y", side="right", showgrid=False),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de faturamento.")

# --- Top 5 fornecedores ---
with col_dir:
    st.subheader(f"Top 5 Fornecedores — {periodo_label}")
    if top5_forn:
        nomes = [
            (r.nome_part or r.cnpj_part or r.cod_part or "N/I")[:30]
            for r in top5_forn
        ]
        valores = [r.total_compras or 0.0 for r in top5_forn]

        fig_forn = go.Figure(go.Bar(
            x=valores,
            y=nomes,
            orientation="h",
            marker_color=AZUL,
            text=[fmt_brl_int(v) for v in valores],
            textposition="outside",
        ))
        fig_forn.update_layout(
            **PLOTLY_LAYOUT,
            xaxis_title="Valor (R$)",
            height=320,
            showlegend=False,
        )
        st.plotly_chart(fig_forn, use_container_width=True)
    else:
        st.info("Sem dados de fornecedores.")

# ------------------------------------------------------------------
# Composição por departamento
# ------------------------------------------------------------------

if composicao_depto:
    st.divider()
    st.subheader(f"Faturamento por Departamento — {periodo_label}")
    df_dep = pd.DataFrame(composicao_depto)
    df_dep = df_dep.sort_values("valor", ascending=True)
    total_dep = df_dep["valor"].sum()
    df_dep["pct"] = df_dep["valor"] / total_dep * 100 if total_dep else 0.0

    fig_dep = go.Figure(go.Bar(
        x=df_dep["valor"],
        y=df_dep["departamento"],
        orientation="h",
        marker_color=AZUL,
        text=[f"{fmt_brl_int(v)} ({p:.1f}%)" for v, p in zip(df_dep["valor"], df_dep["pct"])],
        textposition="outside",
    ))
    fig_dep.update_layout(
        **PLOTLY_LAYOUT,
        xaxis_title="Valor (R$)",
        height=max(320, len(df_dep) * 28 + 80),
        showlegend=False,
    )
    st.plotly_chart(fig_dep, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# Rodapé informativo
# ------------------------------------------------------------------

col_i1, col_i2, col_i3 = st.columns(3)

# Última data contemplada nos dados
ultima_data = None
if meses_v:
    ultimo_mes = meses_v[0]
    # periodo_fin do arquivo mais recente
    if ultimo_arq and ultimo_arq.periodo_fin:
        raw = ultimo_arq.periodo_fin  # YYYYMMDD
        ultima_data = f"{raw[6:8]}/{raw[4:6]}/{raw[0:4]}"
    else:
        ultima_data = f"até {MESES_NOME.get(ultimo_mes[4:], ultimo_mes[4:])}/{ultimo_mes[:4]}"

col_i1.metric(
    "Última data nos dados",
    ultima_data or "—",
    help="Data final do arquivo EFD mais recente importado",
)

col_i2.metric(
    "Último arquivo",
    ultimo_arq.nome_padronizado if ultimo_arq else "—",
    help="Último arquivo processado com sucesso",
)

if ultimo_arq and ultimo_arq.processado_em:
    col_i3.metric(
        "Importado em",
        ultimo_arq.processado_em.strftime("%d/%m/%Y %H:%M"),
    )
else:
    col_i3.metric("Importado em", "—")
