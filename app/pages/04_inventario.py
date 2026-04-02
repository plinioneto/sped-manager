import pandas as pd
import streamlit as st
import app.models
from app.utils.db import get_session
from app.utils.theme import AZUL, VERDE, VERMELHO, AMBAR
from app.repositories.inventario_repo import InventarioRepository
from app.repositories.estoque_repo import EstoqueRepository
from app.repositories.estoque_virtual_repo import EstoqueVirtualRepository

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

from app.components.sidebar import render_sidebar
render_sidebar()

st.title("Estoque")

MOTIVOS = {
    "01": "Fim de período",
    "02": "Mudança de tributação",
    "03": "Balanço",
    "04": "Encerramento",
    "05": "Outros",
    "06": "Início de atividade",
}

IND_EST_LABEL = {
    "0": "Próprio",
    "1": "De terceiro",
    "2": "Em poder de terceiro",
}

IND_PROP_LABEL = {
    "0": "Próprio",
    "1": "De terceiro",
}


def formatar_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_qtd(valor: float) -> str:
    return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


aba_v, aba_h, aba_k = st.tabs([
    "📊 Estoque Virtual",
    "📦 Inventário (Bloco H)",
    "🗃️ Saldo de Estoque (K200)",
])

# ─── ABA 1: ESTOQUE VIRTUAL ───────────────────────────────────────────────────

with aba_v:

    # Carrega fonte e métricas (sem filtro de busca)
    db = next(get_session())
    try:
        repo_v = EstoqueVirtualRepository(db, st.session_state.tenant_id)
        fonte_info = repo_v.fonte_estoque_inicial()
        metricas_v = repo_v.metricas_virtual()
    finally:
        db.close()

    # Banner informativo de fonte
    data_fmt = (
        fonte_info["data_base"].strftime("%d/%m/%Y")
        if fonte_info["data_base"]
        else None
    )

    if fonte_info["fonte"] == "k200":
        st.info(
            f"📋 Saldo inicial baseado no **K200** (Bloco K)  |  "
            f"Data base: **{data_fmt}**  |  "
            "Movimentações consideradas a partir dessa data."
        )
    elif fonte_info["fonte"] == "h010":
        st.warning(
            f"📦 Saldo inicial baseado no **Inventário H010** (Bloco H)  |  "
            f"Data base: **{data_fmt}**  |  "
            "Bloco K não encontrado — usando inventário físico como ponto de partida."
        )
    else:
        st.warning(
            "⚠️ Nenhum inventário (Bloco H ou K) encontrado. "
            "Saldo inicial considerado **zero** — toda a movimentação importada é considerada."
        )

    # Cards de métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de SKUs", metricas_v["total_skus"])
    col2.metric("Com saldo positivo", metricas_v["skus_positivo"])
    col3.metric("Com saldo negativo", metricas_v["skus_negativo"])
    col4.metric("Zerados", metricas_v["skus_zerado"])

    # Alerta de inconsistência
    if metricas_v["total_skus"] > 0:
        pct_neg = metricas_v["skus_negativo"] / metricas_v["total_skus"]
        if pct_neg > 0.10:
            st.error(
                f"⚠️ {metricas_v['skus_negativo']} produto(s) com saldo negativo "
                f"({pct_neg:.0%} do total). Isso pode indicar notas de saída sem a "
                "entrada correspondente importada no SPED."
            )

    st.divider()

    # Filtro de busca
    busca_v = st.text_input(
        "Buscar produto (código ou descrição)",
        placeholder="Ex: 0001 ou arroz",
        key="busca_estoque_virtual",
    )

    # Carrega tabela com filtro
    db = next(get_session())
    try:
        repo_v = EstoqueVirtualRepository(db, st.session_state.tenant_id)
        saldos_v = repo_v.saldo_virtual(busca_v or None)
    finally:
        db.close()

    if not saldos_v:
        st.info("Nenhum produto encontrado.")
    else:
        df_v = pd.DataFrame(saldos_v)
        df_v.rename(columns={
            "cod_item":    "Código",
            "descr_item":  "Produto",
            "unid":        "Unidade",
            "qt_inicial":  "Estoque Inicial",
            "qt_entradas": "Entradas",
            "qt_saidas":   "Saídas",
            "qt_atual":    "Saldo Atual",
        }, inplace=True)

        st.dataframe(
            df_v[["Código", "Produto", "Unidade",
                  "Estoque Inicial", "Entradas", "Saídas", "Saldo Atual"]],
            use_container_width=True,
            column_config={
                "Estoque Inicial": st.column_config.NumberColumn(format="%.3f"),
                "Entradas":        st.column_config.NumberColumn(format="%.3f"),
                "Saídas":          st.column_config.NumberColumn(format="%.3f"),
                "Saldo Atual":     st.column_config.NumberColumn(format="%.3f"),
            },
            hide_index=True,
        )

        st.caption(f"**{len(saldos_v)} produto(s)** exibido(s)")

# ─── ABA 2: INVENTÁRIO (BLOCO H) ──────────────────────────────────────────────

with aba_h:
    db = next(get_session())
    try:
        repo = InventarioRepository(db, st.session_state.tenant_id)
        inventarios = repo.datas_disponiveis()
    finally:
        db.close()

    if not inventarios:
        st.info("Nenhum inventário encontrado. Importe um arquivo EFD que contenha o Bloco H.")
    else:
        mais_recente = inventarios[0]

        db = next(get_session())
        try:
            repo = InventarioRepository(db, st.session_state.tenant_id)
            total_itens_rec = repo.total_itens(mais_recente.id)
        finally:
            db.close()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Inventários importados", len(inventarios))
        col2.metric("Data mais recente", mais_recente.dt_inv.strftime("%d/%m/%Y"))
        col3.metric("Valor total (mais recente)", formatar_br(mais_recente.vl_inv or 0))
        col4.metric("Itens (mais recente)", total_itens_rec)

        st.divider()

        opcoes = {
            f"{inv.dt_inv.strftime('%d/%m/%Y')} — {MOTIVOS.get(inv.mot_inv, inv.mot_inv)}": inv.id
            for inv in inventarios
        }
        selecionado_label = st.selectbox("Selecionar inventário", list(opcoes.keys()))
        inventario_id = opcoes[selecionado_label]

        db = next(get_session())
        try:
            repo = InventarioRepository(db, st.session_state.tenant_id)
            itens = repo.listar_itens(inventario_id)
        finally:
            db.close()

        if not itens:
            st.info("Este inventário não possui itens registrados.")
        else:
            rows = []
            for h010, produto in itens:
                rows.append({
                    "Código": h010.cod_item,
                    "Descrição": produto.descr_item if produto else "—",
                    "Unidade": h010.unid or "—",
                    "Quantidade": h010.qtd or 0.0,
                    "Vlr. Unit.": h010.vl_unit or 0.0,
                    "Vlr. Total": h010.vl_item or 0.0,
                    "Propriedade": IND_PROP_LABEL.get(h010.ind_prop, h010.ind_prop or "—"),
                    "Cód. Participante": h010.cod_part or "—",
                })

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Quantidade": st.column_config.NumberColumn(format="%.3f"),
                    "Vlr. Unit.": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Vlr. Total": st.column_config.NumberColumn(format="R$ %.2f"),
                },
                hide_index=True,
            )

            total_itens = len(rows)
            valor_total = sum(r["Vlr. Total"] for r in rows)
            st.caption(
                f"**Total de itens:** {total_itens}  |  "
                f"**Valor total do inventário:** {formatar_br(valor_total)}"
            )

# ─── ABA 3: SALDO K200 ────────────────────────────────────────────────────────

with aba_k:
    db = next(get_session())
    try:
        repo = EstoqueRepository(db, st.session_state.tenant_id)
        datas_k200 = repo.datas_disponiveis()
    finally:
        db.close()

    if not datas_k200:
        st.info("Nenhum saldo de estoque encontrado. Importe um arquivo EFD que contenha o Bloco K.")
    else:
        data_mais_recente = datas_k200[0].dt_est

        db = next(get_session())
        try:
            repo = EstoqueRepository(db, st.session_state.tenant_id)
            metricas = repo.metricas_k200(dt_est=data_mais_recente)
        finally:
            db.close()

        col1, col2, col3 = st.columns(3)
        col1.metric("Saldo mais recente", data_mais_recente.strftime("%d/%m/%Y"))
        col2.metric("Itens com saldo > 0", metricas["total_itens"])
        col3.metric("Total de unidades", formatar_qtd(metricas["total_unidades"]))

        st.divider()

        col_data, col_busca = st.columns([1, 2])
        with col_data:
            opcoes_data = {d.dt_est.strftime("%d/%m/%Y"): d.dt_est for d in datas_k200}
            data_label = st.selectbox("Data do saldo", list(opcoes_data.keys()))
            dt_selecionada = opcoes_data[data_label]
        with col_busca:
            busca = st.text_input(
                "Buscar produto (código ou descrição)",
                placeholder="Ex: 0001 ou arroz",
                key="busca_k200",
            )

        db = next(get_session())
        try:
            repo = EstoqueRepository(db, st.session_state.tenant_id)
            saldos = repo.saldo_por_data(dt_selecionada, busca or None)
        finally:
            db.close()

        if not saldos:
            st.info("Nenhum item encontrado para os filtros selecionados.")
        else:
            rows = []
            for k200, produto in saldos:
                rows.append({
                    "Código": k200.cod_item,
                    "Descrição": produto.descr_item if produto else "—",
                    "Unidade": produto.unid_inv if produto else "—",
                    "Saldo em Estoque": k200.qt_est or 0.0,
                    "Tipo": IND_EST_LABEL.get(k200.ind_est, k200.ind_est or "—"),
                })

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Saldo em Estoque": st.column_config.NumberColumn(format="%.3f"),
                },
                hide_index=True,
            )

            st.caption(f"**{len(rows)} itens** exibidos")
