import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_session
from app.utils.formatters import formatar_cnpj
from app.repositories.compras_repo import ComprasRepository
from app.models.categoria import Departamento, Grupo, Categoria
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

MESES_ABREV = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
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
    "1102": "Mercadoria p/ Revenda", "1403": "Mercadoria p/ Revenda",
    "2102": "Mercadoria p/ Revenda", "2403": "Mercadoria p/ Revenda",
    "1152": "Transferências", "1409": "Transferências",
    "1101": "Industrialização",
    "1407": "Uso e Consumo", "1556": "Uso e Consumo",
    "2407": "Uso e Consumo", "2556": "Uso e Consumo",
    "1406": "Ativo Imobilizado", "1551": "Ativo Imobilizado",
    "2406": "Ativo Imobilizado", "2551": "Ativo Imobilizado",
    "1652": "Energia Elétrica", "1653": "Energia Elétrica",
    "1910": "Bonificação/Doação", "2910": "Bonificação/Doação",
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


def formatar_mes_curto(yyyymm: str) -> str:
    ano = yyyymm[:4]
    mes = yyyymm[4:6]
    return f"{mes}/{ano}"


def cnpj_curto(cnpj: str) -> str:
    if cnpj and len(cnpj) == 14:
        return formatar_cnpj(cnpj)
    return cnpj or "N/I"


def nome_fornecedor(row) -> str:
    nome = getattr(row, "nome_part", None)
    if nome:
        return nome
    cnpj = getattr(row, "cnpj_part", None)
    if cnpj and len(cnpj) == 14:
        return formatar_cnpj(cnpj)
    cod = getattr(row, "cod_part", None)
    return cnpj_curto(cod) if cod else "N/I"


# ---------------------------------------------------------------------------
# Título
# ---------------------------------------------------------------------------

st.title("Gestão de Compras")
st.divider()

# ---------------------------------------------------------------------------
# Filtro Row 1 — Período + Loja (placeholder multi-store)
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo_init = ComprasRepository(db, tenant_id)
    meses_raw = repo_init.meses_disponiveis()
finally:
    db.close()

anos_raw = sorted({m[:4] for m in meses_raw}, reverse=True)
meses_num_raw = sorted({m[4:] for m in meses_raw})

lojas = st.session_state.get("lojas_disponiveis", [])
mostrar_loja = len(lojas) > 1

if mostrar_loja:
    col_ano, col_mes, col_loja = st.columns([1, 2, 2])
else:
    col_ano, col_mes = st.columns([1, 2])

sel_ano = col_ano.selectbox("Ano", ["Todos"] + anos_raw, key="compras_ano")
sel_meses = col_mes.multiselect(
    "Mês",
    options=meses_num_raw,
    format_func=lambda m: MESES_ABREV.get(m, m),
    placeholder="Todos",
    key="compras_meses",
)

if mostrar_loja:
    col_loja.multiselect(
        "Loja",
        options=[l["id"] for l in lojas],
        format_func=lambda lid: next((l["nome"] for l in lojas if l["id"] == lid), str(lid)),
        placeholder="Todas as lojas",
        key="compras_lojas",
    )

ano_filtro = None if sel_ano == "Todos" else sel_ano
meses_filtro = sel_meses if sel_meses else None

# ---------------------------------------------------------------------------
# Filtro Row 2 — Hierarquia cascateada (Departamento > Grupo > Categoria)
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    deptos = db.query(Departamento).order_by(Departamento.descricao).all()
    opcoes_depto = {d.descricao: d.id for d in deptos}

    col_d, col_g, col_c = st.columns(3)

    stored_depto = st.session_state.get("compras_depto", "Todos")
    depto_opts = ["Todos"] + list(opcoes_depto.keys())
    depto_index = depto_opts.index(stored_depto) if stored_depto in depto_opts else 0
    sel_depto_nome = col_d.selectbox("Departamento", depto_opts, index=depto_index, key="compras_depto")
    departamento_id = opcoes_depto.get(sel_depto_nome)

    grupo_id = None
    sel_grupo_nome = "Todos"
    categoria_id = None
    sel_cat_nome = "Todos"

    if departamento_id:
        grupos = (
            db.query(Grupo)
            .filter(Grupo.departamento_id == departamento_id)
            .order_by(Grupo.descricao)
            .all()
        )
        opcoes_grupo = {g.descricao: g.id for g in grupos}
        grupo_opts = ["Todos"] + list(opcoes_grupo.keys())
        stored_grupo = st.session_state.get("compras_grupo", "Todos")
        grupo_index = grupo_opts.index(stored_grupo) if stored_grupo in grupo_opts else 0
        sel_grupo_nome = col_g.selectbox("Grupo", grupo_opts, index=grupo_index, key="compras_grupo")
        grupo_id = opcoes_grupo.get(sel_grupo_nome)

        if grupo_id:
            cats = (
                db.query(Categoria)
                .filter(Categoria.grupo_id == grupo_id)
                .order_by(Categoria.descricao)
                .all()
            )
            opcoes_cat = {c.descricao: c.id for c in cats}
            cat_opts = ["Todos"] + list(opcoes_cat.keys())
            stored_cat = st.session_state.get("compras_cat", "Todos")
            cat_index = cat_opts.index(stored_cat) if stored_cat in cat_opts else 0
            sel_cat_nome = col_c.selectbox("Categoria", cat_opts, index=cat_index, key="compras_cat")
            categoria_id = opcoes_cat.get(sel_cat_nome)
finally:
    db.close()

filtros = dict(ano=ano_filtro, meses=meses_filtro, fornecedor=None, num_nota=None, produto=None)
hier = dict(departamento_id=departamento_id, grupo_id=grupo_id, categoria_id=categoria_id)

# Breadcrumb do filtro ativo
partes_hier = []
if departamento_id:
    partes_hier.append(sel_depto_nome)
if grupo_id:
    partes_hier.append(sel_grupo_nome)
if categoria_id:
    partes_hier.append(sel_cat_nome)
if partes_hier:
    st.caption(f"🔍 Filtro ativo: **{' › '.join(partes_hier)}**")

st.divider()

# ---------------------------------------------------------------------------
# Carregamento principal de dados
# ---------------------------------------------------------------------------

db = next(get_session())
try:
    repo = ComprasRepository(db, tenant_id)

    metricas = repo.metricas_globais(**filtros)
    evolucao = repo.evolucao_mensal(**filtros)
    cfop_data = repo.distribuicao_cfop(**filtros)
    por_fornecedor = repo.agrupar_por_fornecedor(**filtros, **hier)
    forn_evolucao = repo.top_fornecedores_evolucao(limit=5, **filtros)
    dados_fabricante = repo.agrupar_por_fabricante(**hier, **filtros)
    dados_marca = repo.agrupar_por_marca(**hier, **filtros)

    # Dados do nível hierárquico ativo
    if categoria_id:
        nivel_dados = repo.agrupar_por_produto_categoria(categoria_id, **filtros)
        nivel_tipo = "produto"
        nivel_titulo = f"Produtos em {sel_cat_nome}"
    elif grupo_id:
        nivel_dados = repo.agrupar_por_categoria(grupo_id, **filtros)
        nivel_tipo = "categoria"
        nivel_titulo = f"Por Categoria — {sel_grupo_nome}"
    elif departamento_id:
        nivel_dados = repo.agrupar_por_grupo(departamento_id, **filtros)
        nivel_tipo = "grupo"
        nivel_titulo = f"Por Grupo — {sel_depto_nome}"
    else:
        nivel_dados = repo.agrupar_por_departamento(**filtros)
        nivel_tipo = "departamento"
        nivel_titulo = "Por Departamento"

    # Delta para cards (mês único selecionado)
    delta_notas = delta_forn = delta_valor = delta_itens = None
    if ano_filtro and meses_filtro and len(meses_filtro) == 1 and len(meses_raw) > 1:
        yyyymm = ano_filtro + meses_filtro[0]
        idx = meses_raw.index(yyyymm) if yyyymm in meses_raw else -1
        if idx >= 0 and idx + 1 < len(meses_raw):
            mes_ant = meses_raw[idx + 1]
            filtros_ant = dict(ano=mes_ant[:4], meses=[mes_ant[4:]], fornecedor=None, num_nota=None, produto=None)
            m_ant = repo.metricas_globais(**filtros_ant)
            delta_notas = metricas["total_notas"] - m_ant["total_notas"]
            delta_forn = metricas["total_fornecedores"] - m_ant["total_fornecedores"]
            delta_valor = metricas["valor_total_compras"] - m_ant["valor_total_compras"]
            delta_itens = metricas["total_itens_comprados"] - m_ant["total_itens_comprados"]

finally:
    db.close()

# Totais do nível hierárquico
if nivel_tipo == "produto":
    grand_total_nivel = sum(r.vl_total or 0.0 for r in nivel_dados)
else:
    grand_total_nivel = sum(r.valor or 0.0 for r in nivel_dados)

valor_card = grand_total_nivel if any(hier.values()) else metricas["valor_total_compras"]

if nivel_tipo == "produto":
    skus_card = len(nivel_dados)
    skus_label = "Produtos no nível"
else:
    skus_card = sum(getattr(r, "qtd_skus", 0) or 0 for r in nivel_dados)
    skus_label = "SKUs distintos" if any(hier.values()) else "Itens comprados"

# ---------------------------------------------------------------------------
# Cards de resumo
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Valor Total Compras",
    formatar_br(valor_card),
    delta=f"{formatar_br(delta_valor)} vs mês anterior" if delta_valor is not None else None,
)
col2.metric(
    "Notas de Entrada",
    f"{metricas['total_notas']:,}".replace(",", "."),
    delta=f"{delta_notas:+d} vs mês anterior" if delta_notas is not None else None,
)
col3.metric(
    "Fornecedores",
    f"{metricas['total_fornecedores']:,}".replace(",", "."),
    delta=f"{delta_forn:+d} vs mês anterior" if delta_forn is not None else None,
)
col4.metric(
    skus_label,
    f"{skus_card:,}".replace(",", "."),
    delta=f"{delta_itens:+d} vs mês anterior" if delta_itens is not None and nivel_tipo not in ("produto",) else None,
)

st.divider()

# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

aba_geral, aba_cat, aba_forn, aba_notas = st.tabs([
    "Visão Geral",
    "Por Categoria",
    "Fornecedores",
    "Notas e Itens",
])

# ===========================================================================
# ABA 1 — VISÃO GERAL
# ===========================================================================

with aba_geral:

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

    st.divider()

    # --- Share por Fabricante e Marca ---
    st.subheader("Share por Fabricante e Marca")

    col_fab, col_marc = st.columns(2)

    with col_fab:
        st.markdown("**Top 10 Fabricantes**")
        if dados_fabricante:
            grand_fab = sum(r.valor or 0.0 for r in dados_fabricante)
            top10_fab = dados_fabricante[:10]
            df_fab = pd.DataFrame([{
                "Fabricante": (r.nome or "Sem fabricante")[:35],
                "Valor (R$)": r.valor or 0.0,
                "Share (%)": (r.valor or 0.0) / grand_fab * 100 if grand_fab else 0.0,
            } for r in top10_fab])
            df_fab = df_fab.sort_values("Valor (R$)", ascending=True)

            fig_fab = go.Figure(go.Bar(
                x=df_fab["Valor (R$)"],
                y=df_fab["Fabricante"],
                orientation="h",
                marker_color=AZUL,
                text=[f"{p:.1f}%" for p in df_fab["Share (%)"]],
                textposition="outside",
                textfont=dict(size=10),
            ))
            fig_fab.update_layout(
                **PLOTLY_LAYOUT,
                xaxis_title="Valor (R$)",
                height=max(300, len(df_fab) * 30 + 60),
                showlegend=False,
            )
            st.plotly_chart(fig_fab, use_container_width=True)

            # Aviso se maioria sem fabricante
            sem_fab = next((r for r in dados_fabricante if r.nome == "Sem fabricante"), None)
            if sem_fab and grand_fab:
                pct_sem = (sem_fab.valor or 0.0) / grand_fab * 100
                if pct_sem > 20:
                    st.caption(f"⚠️ {pct_sem:.0f}% dos itens sem fabricante classificado")
        else:
            st.info("Nenhum fabricante identificado. Vincule marcas aos produtos no cadastro.")

    with col_marc:
        st.markdown("**Top 10 Marcas**")
        if dados_marca:
            grand_marc = sum(r.valor or 0.0 for r in dados_marca)
            top10_marc = dados_marca[:10]
            df_marc = pd.DataFrame([{
                "Marca": (r.nome or "Sem marca")[:35],
                "Fabricante": r.fabricante_nome or "—",
                "Valor (R$)": r.valor or 0.0,
                "Share (%)": (r.valor or 0.0) / grand_marc * 100 if grand_marc else 0.0,
            } for r in top10_marc])
            df_marc = df_marc.sort_values("Valor (R$)", ascending=True)

            fig_marc = go.Figure(go.Bar(
                x=df_marc["Valor (R$)"],
                y=df_marc["Marca"],
                orientation="h",
                marker_color=VERDE,
                text=[f"{p:.1f}%" for p in df_marc["Share (%)"]],
                textposition="outside",
                textfont=dict(size=10),
            ))
            fig_marc.update_layout(
                **PLOTLY_LAYOUT,
                xaxis_title="Valor (R$)",
                height=max(300, len(df_marc) * 30 + 60),
                showlegend=False,
            )
            st.plotly_chart(fig_marc, use_container_width=True)

            sem_marc = next((r for r in dados_marca if r.nome == "Sem marca"), None)
            if sem_marc and grand_marc:
                pct_sem = (sem_marc.valor or 0.0) / grand_marc * 100
                if pct_sem > 20:
                    st.caption(f"⚠️ {pct_sem:.0f}% dos itens sem marca classificada")
        else:
            st.info("Nenhuma marca identificada. Vincule marcas aos produtos no cadastro.")

    st.divider()

    # --- Distribuição por CFOP ---
    if cfop_data:
        st.subheader("Distribuição por Finalidade (CFOP)")
        grupos_cfop = {}
        for r in cfop_data:
            grupo = CFOP_GRUPO.get(r.cfop, "Outros") if r.cfop else "Outros"
            if grupo not in grupos_cfop:
                grupos_cfop[grupo] = {"Valor (R$)": 0.0, "Itens": 0}
            grupos_cfop[grupo]["Valor (R$)"] += r.valor_total or 0.0
            grupos_cfop[grupo]["Itens"] += r.qtd_itens or 0

        df_cfop = pd.DataFrame([
            {"Finalidade": g, "Valor (R$)": v["Valor (R$)"], "Itens": v["Itens"]}
            for g, v in grupos_cfop.items()
        ]).sort_values("Valor (R$)", ascending=False)

        cores_grupo = {
            "Mercadoria p/ Revenda": AZUL,
            "Transferências": COLOR_SEQ[5] if len(COLOR_SEQ) > 5 else "#7986CB",
            "Industrialização": AMBAR,
            "Uso e Consumo": COLOR_SEQ[4] if len(COLOR_SEQ) > 4 else "#4DB6AC",
            "Ativo Imobilizado": COLOR_SEQ[1] if len(COLOR_SEQ) > 1 else "#F48FB1",
            "Energia Elétrica": COLOR_SEQ[2] if len(COLOR_SEQ) > 2 else "#80CBC4",
            "Bonificação/Doação": VERMELHO,
            "Outros": "#97A0AF",
        }

        import plotly.express as px
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

        with st.expander("Ver detalhamento por CFOP"):
            df_detalhe = pd.DataFrame([{
                "CFOP": r.cfop or "N/I",
                "Descrição": CFOP_DESCR.get(r.cfop, "Outros") if r.cfop else "N/I",
                "Finalidade": CFOP_GRUPO.get(r.cfop, "Outros") if r.cfop else "Outros",
                "Valor (R$)": r.valor_total or 0.0,
                "Itens": r.qtd_itens or 0,
            } for r in cfop_data])
            st.dataframe(df_detalhe, use_container_width=True, hide_index=True,
                         column_config={"Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")})


# ===========================================================================
# ABA 2 — POR CATEGORIA (macro → micro)
# ===========================================================================

with aba_cat:

    st.subheader(nivel_titulo)
    st.caption(f"Nível: **{'›'.join(partes_hier) if partes_hier else 'Todos os Departamentos'}**")

    if not nivel_dados:
        st.info("Nenhum dado encontrado. Verifique se os produtos estão classificados.")
    else:
        # Cards do nível
        total_itens_nivel = sum(getattr(r, "qtd_itens", 0) or 0 for r in nivel_dados) if nivel_tipo != "produto" else len(nivel_dados)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Valor Total", formatar_br(grand_total_nivel))
        col_m2.metric("SKUs distintos" if nivel_tipo != "produto" else "Produtos", f"{skus_card:,}".replace(",", "."))
        col_m3.metric("Linhas de compra" if nivel_tipo != "produto" else "SKUs", f"{total_itens_nivel:,}".replace(",", "."))

        # Gráfico de barras horizontais
        if nivel_tipo == "produto":
            nomes_chart = [(r.descricao_padrao or r.descr_item or r.cod_item or "—")[:40] for r in nivel_dados[:25]]
            valores_chart = [r.vl_total or 0.0 for r in nivel_dados[:25]]
        else:
            nomes_chart = [(r.nome or "Não classificado")[:40] for r in nivel_dados[:25]]
            valores_chart = [r.valor or 0.0 for r in nivel_dados[:25]]

        pares = sorted(zip(valores_chart, nomes_chart), key=lambda x: x[0])
        valores_ord = [p[0] for p in pares]
        nomes_ord = [p[1] for p in pares]
        pcts_ord = [v / grand_total_nivel * 100 if grand_total_nivel else 0.0 for v in valores_ord]

        fig_cat = go.Figure(go.Bar(
            x=valores_ord,
            y=nomes_ord,
            orientation="h",
            marker_color=AZUL,
            text=[f"{formatar_br(v)} ({p:.1f}%)" for v, p in zip(valores_ord, pcts_ord)],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_cat.update_layout(
            **PLOTLY_LAYOUT,
            xaxis_title="Valor (R$)",
            height=max(360, len(nomes_ord) * 28 + 80),
            showlegend=False,
        )
        st.plotly_chart(fig_cat, use_container_width=True)

        # Tabela detalhada
        if nivel_tipo == "produto":
            df_cat = pd.DataFrame([{
                "Código": r.cod_item or "—",
                "Descrição": r.descricao_padrao or r.descr_item or "—",
                "Unidade": r.unid_inv or "—",
                "Qtd. Total": r.qtd_total or 0.0,
                "Valor Total (R$)": r.vl_total or 0.0,
                "% do Nível": (r.vl_total or 0.0) / grand_total_nivel * 100 if grand_total_nivel else 0.0,
                "Nº Notas": r.qtd_notas or 0,
            } for r in nivel_dados])
            st.dataframe(df_cat, use_container_width=True, hide_index=True, column_config={
                "Qtd. Total": st.column_config.NumberColumn(format="%.3f"),
                "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "% do Nível": st.column_config.NumberColumn(format="%.1f %%"),
            })
        else:
            df_cat = pd.DataFrame([{
                "Nome": r.nome or "Não classificado",
                "Valor Total (R$)": r.valor or 0.0,
                "% do Total": (r.valor or 0.0) / grand_total_nivel * 100 if grand_total_nivel else 0.0,
                "Linhas": r.qtd_itens or 0,
                "SKUs": r.qtd_skus or 0,
            } for r in nivel_dados])
            st.dataframe(df_cat, use_container_width=True, hide_index=True, column_config={
                "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "% do Total": st.column_config.NumberColumn(format="%.1f %%"),
            })

        st.caption(f"{len(nivel_dados)} registro(s) | Total: {formatar_br(grand_total_nivel)}")


# ===========================================================================
# ABA 3 — FORNECEDORES
# ===========================================================================

with aba_forn:

    if not por_fornecedor:
        st.info("Nenhum fornecedor encontrado para os filtros selecionados.")
    else:
        grand_total_forn = sum(r.total_compras or 0.0 for r in por_fornecedor)

        # --- Pareto de fornecedores ---
        st.subheader("Concentração de Fornecedores (Pareto)")

        acumulado = 0.0
        pareto_data = []
        for r in por_fornecedor:
            val = r.total_compras or 0.0
            acumulado += val
            pareto_data.append({
                "Fornecedor": nome_fornecedor(r),
                "Valor (R$)": val,
                "% Acumulado": (acumulado / grand_total_forn * 100) if grand_total_forn else 0.0,
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

            import plotly.express as px
            fig_forn_evo = px.line(
                df_forn_evo, x="Mês", y="Valor (R$)", color="Fornecedor",
                markers=True,
            )
            fig_forn_evo.update_layout(**PLOTLY_LAYOUT, height=380)
            st.plotly_chart(fig_forn_evo, use_container_width=True)

        # --- Tabela ranking ---
        st.subheader("Ranking de Fornecedores")

        df_forn = pd.DataFrame([{
            "Fornecedor": nome_fornecedor(r),
            "CNPJ": formatar_cnpj(r.cnpj_part) if r.cnpj_part and len(r.cnpj_part) == 14 else (r.cnpj_part or "—"),
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
        st.caption(f"{len(por_fornecedor)} fornecedor(es) | Total: {formatar_br(grand_total_forn)}")
        if partes_hier:
            st.caption(f"ℹ️ Filtrado por: {' › '.join(partes_hier)}")


# ===========================================================================
# ABA 4 — NOTAS E ITENS
# ===========================================================================

with aba_notas:

    # Filtros locais da aba
    col_forn_det, col_nota_det, col_prod_det = st.columns(3)
    busca_forn = col_forn_det.text_input("Fornecedor", placeholder="CNPJ ou parte do nome", key="compras_forn_det")
    busca_nota = col_nota_det.text_input("Nº da Nota", placeholder="Ex: 000123456", key="compras_nota_det")
    busca_prod = col_prod_det.text_input("Produto", placeholder="Código ou descrição", key="compras_prod_det")

    filtros_det = dict(
        ano=ano_filtro,
        meses=meses_filtro,
        fornecedor=busca_forn.strip() or None,
        num_nota=busca_nota.strip() or None,
        produto=busca_prod.strip() or None,
    )

    # --- Notas de Entrada ---
    st.subheader("Notas de Entrada")

    db = next(get_session())
    try:
        repo = ComprasRepository(db, tenant_id)
        notas = repo.listar_notas(**filtros_det)
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
        itens_rows = repo.listar_itens(**filtros_det)
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
