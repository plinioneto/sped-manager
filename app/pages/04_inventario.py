import streamlit as st
import app.models
from app.utils.db import get_session
from app.repositories.inventario_repo import InventarioRepository
from app.repositories.estoque_repo import EstoqueRepository

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

from app.components.sidebar import render_sidebar
render_sidebar()

st.title("Estoque — Inventário e Saldos")

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


aba_h, aba_k = st.tabs(["📦 Inventário (Bloco H)", "📊 Saldo de Estoque (K200)"])

# ─── ABA 1: INVENTÁRIO ────────────────────────────────────────────────────────

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

            import pandas as pd
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

# ─── ABA 2: SALDO K200 ────────────────────────────────────────────────────────

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
            busca = st.text_input("Buscar produto (código ou descrição)", placeholder="Ex: 0001 ou arroz")

        db = next(get_session())
        try:
            repo = EstoqueRepository(db, st.session_state.tenant_id)
            saldos = repo.saldo_por_data(dt_selecionada, busca or None)
        finally:
            db.close()

        if not saldos:
            st.info("Nenhum item encontrado para os filtros selecionados.")
        else:
            import pandas as pd
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
