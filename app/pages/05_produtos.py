import streamlit as st
import pandas as pd
from sqlalchemy import func

import app.models
from app.components.sidebar import render_sidebar
from app.utils.db import get_db
from app.models.produto import Produto
from app.models.marca import Marca
from app.models.fabricante import Fabricante
from app.models.categoria import Departamento, Grupo, Categoria
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.participante import Participante

if not st.session_state.get("tenant_id"):
    st.switch_page("main.py")

render_sidebar()

tenant_id = st.session_state.tenant_id

st.title("Produtos")
st.divider()

with get_db() as db:
    produtos = (
        db.query(Produto)
        .filter(Produto.tenant_id == tenant_id)
        .order_by(Produto.descr_item)
        .all()
    )

if not produtos:
    st.info("Nenhum produto cadastrado. Importe um arquivo EFD para popular o cadastro.")
    st.stop()

# ── Métricas gerais ───────────────────────────────────────────────────────────
total   = len(produtos)
ativos  = sum(1 for p in produtos if p.ativo)
com_cat = sum(1 for p in produtos if p.categoria_id)
com_mrc = sum(1 for p in produtos if p.marca_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de produtos",    f"{total:,}".replace(",", "."))
c2.metric("Ativos",               f"{ativos:,}".replace(",", "."))
c3.metric("Classificados",        f"{com_cat:,}".replace(",", "."),
          delta=f"{com_cat/total:.0%}" if total else None)
c4.metric("Com marca identificada", f"{com_mrc:,}".replace(",", "."),
          delta=f"{com_mrc/total:.0%}" if total else None)

st.divider()

aba_cadastro, aba_padronizacao, aba_inteligencia = st.tabs([
    "Cadastro EFD", "Padronização & Categorias", "Inteligência de Produtos"
])

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 1 — Cadastro EFD
# ═══════════════════════════════════════════════════════════════════════════════

with aba_cadastro:

    tipos = sorted({p.tipo_item for p in produtos if p.tipo_item})
    ncms  = sorted({p.cod_ncm for p in produtos if p.cod_ncm})

    cf1, cf2, cf3 = st.columns([3, 1, 1])
    busca    = cf1.text_input("Buscar por código ou descrição", placeholder="Digite código ou descrição...")
    tipo_sel = cf2.selectbox("Tipo de item", ["Todos"] + tipos)
    ncm_sel  = cf3.selectbox("NCM", ["Todos"] + ncms)

    filtrados = produtos

    if busca:
        termo = busca.lower()
        filtrados = [
            p for p in filtrados
            if termo in (p.cod_item or "").lower() or termo in (p.descr_item or "").lower()
        ]
    if tipo_sel != "Todos":
        filtrados = [p for p in filtrados if p.tipo_item == tipo_sel]
    if ncm_sel != "Todos":
        filtrados = [p for p in filtrados if p.cod_ncm == ncm_sel]

    st.caption(f"{len(filtrados)} produto(s) encontrado(s)")

    TIPO_ITEM = {
        "00": "Mercadoria p/ Revenda", "01": "Matéria-Prima", "02": "Embalagem",
        "03": "Prod. em Processo",     "04": "Prod. Acabado", "05": "Subproduto",
        "06": "Prod. Intermediário",   "07": "Mat. Uso e Consumo",
        "08": "Ativo Imobilizado",     "09": "Serviços",
        "10": "Outros Insumos",        "99": "Outras",
    }

    rows = []
    for p in filtrados:
        rows.append({
            "Código":        p.cod_item,
            "Descrição":     p.descr_item,
            "Cód. Barras":   p.cod_barra or "—",
            "Unidade":       p.unid_inv or "—",
            "Tipo":          TIPO_ITEM.get(p.tipo_item, p.tipo_item or "—"),
            "NCM":           p.cod_ncm or "—",
            "CEST":          p.cest or "—",
            "Alíq. ICMS (%)": p.aliq_icms if p.aliq_icms is not None else "—",
            "Ativo":         "Sim" if p.ativo else "Não",
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Alíq. ICMS (%)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 2 — Padronização & Categorias
# ═══════════════════════════════════════════════════════════════════════════════

with aba_padronizacao:

    # Filtros
    pf1, pf2, pf3, pf4 = st.columns([3, 2, 2, 1])

    busca_pad = pf1.text_input("Buscar", placeholder="Código ou descrição...", key="busca_pad")

    deps  = sorted({p.departamento_id for p in produtos if p.departamento_id})
    grps  = sorted({p.grupo_id for p in produtos if p.grupo_id})

    # Carrega nomes para os filtros
    with get_db() as db3:
        dep_nomes = {d.id: d.descricao for d in db3.query(Departamento).all()}
        grp_nomes = {g.id: g.descricao for g in db3.query(Grupo).all()}
        mrc_nomes = {m.id: m.nome for m in db3.query(Marca).all()}

    dep_opcoes = ["Todos"] + [dep_nomes[d] for d in deps if d in dep_nomes]
    dep_sel    = pf2.selectbox("Departamento", dep_opcoes, key="dep_sel_pad")

    situacao_opcoes = ["Todos", "Classificado", "Sem categoria", "Revisão necessária"]
    situacao_sel    = pf3.selectbox("Situação", situacao_opcoes)

    apenas_com_marca = pf4.checkbox("Com marca", value=False)

    # Aplica filtros
    pad_filtrados = produtos

    if busca_pad:
        t = busca_pad.lower()
        pad_filtrados = [
            p for p in pad_filtrados
            if t in (p.cod_item or "").lower()
            or t in (p.descr_item or "").lower()
            or t in (p.descricao_padrao or "").lower()
        ]
    if dep_sel != "Todos":
        dep_id_sel = next((k for k, v in dep_nomes.items() if v == dep_sel), None)
        pad_filtrados = [p for p in pad_filtrados if p.departamento_id == dep_id_sel]
    if situacao_sel == "Classificado":
        pad_filtrados = [p for p in pad_filtrados if p.categoria_id]
    elif situacao_sel == "Sem categoria":
        pad_filtrados = [p for p in pad_filtrados if not p.categoria_id]
    elif situacao_sel == "Revisão necessária":
        pad_filtrados = [p for p in pad_filtrados if p.revisao_necessaria]
    if apenas_com_marca:
        pad_filtrados = [p for p in pad_filtrados if p.marca_id]

    st.caption(f"{len(pad_filtrados)} produto(s)")

    rows_pad = []
    for p in pad_filtrados:
        rows_pad.append({
            "Código":          p.cod_item,
            "Descrição original": p.descr_item,
            "Descrição padronizada": p.descricao_padrao or "—",
            "Marca":           mrc_nomes.get(p.marca_id, "—") if p.marca_id else "—",
            "Embalagem":       p.tipo_embalagem or "—",
            "Qtd":             float(p.peso_volume_valor) if p.peso_volume_valor else None,
            "Unid":            p.peso_volume_unidade or "—",
            "Departamento":    dep_nomes.get(p.departamento_id, "—") if p.departamento_id else "—",
            "Grupo":           grp_nomes.get(p.grupo_id, "—") if p.grupo_id else "—",
            "Score pad.":      float(p.score_padronizacao) if p.score_padronizacao else 0.0,
            "Score cat.":      float(p.score_categoria) if p.score_categoria else 0.0,
            "Revisão":         "Sim" if p.revisao_necessaria else "Não",
            "Origem":          p.origem_padronizacao or "—",
        })

    st.dataframe(
        pd.DataFrame(rows_pad),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score pad.": st.column_config.ProgressColumn(format="%.0%", min_value=0, max_value=1),
            "Score cat.": st.column_config.ProgressColumn(format="%.0%", min_value=0, max_value=1),
        },
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 3 — Inteligência de Produtos
# ═══════════════════════════════════════════════════════════════════════════════

with aba_inteligencia:

    with get_db() as db4:
        # Agrega por produto: qtd total comprada, valor total, nº de fornecedores, tributos
        itens_agg = (
            db4.query(
                ItemFiscal.cod_item,
                func.sum(ItemFiscal.qtd).label("qtd_total"),
                func.sum(ItemFiscal.vl_item).label("vl_total"),
                func.sum(ItemFiscal.vl_icms).label("vl_icms"),
                func.sum(ItemFiscal.vl_pis).label("vl_pis"),
                func.sum(ItemFiscal.vl_cofins).label("vl_cofins"),
                func.count(func.distinct(ItemFiscal.chv_nfe)).label("n_notas"),
            )
            .filter(ItemFiscal.tenant_id == tenant_id)
            .group_by(ItemFiscal.cod_item)
            .all()
        )

        # Conta fornecedores distintos por produto via join com DocumentoFiscal
        from app.models.documento_fiscal import DocumentoFiscal
        forn_por_produto = (
            db4.query(
                ItemFiscal.cod_item,
                func.count(func.distinct(DocumentoFiscal.cod_part)).label("n_fornecedores"),
            )
            .join(DocumentoFiscal, ItemFiscal.chv_nfe == DocumentoFiscal.chv_nfe)
            .filter(ItemFiscal.tenant_id == tenant_id)
            .group_by(ItemFiscal.cod_item)
            .all()
        )
        forn_map = {r.cod_item: r.n_fornecedores for r in forn_por_produto}

    # Constrói mapa produto para nome/marca/categoria
    prod_map = {p.cod_item: p for p in produtos}

    rows_intel = []
    for r in itens_agg:
        p = prod_map.get(r.cod_item)
        if not p:
            continue

        qtd   = r.qtd_total or 0
        valor = r.vl_total or 0
        preco_medio = valor / qtd if qtd > 0 else 0

        vl_icms   = r.vl_icms or 0
        vl_pis    = r.vl_pis or 0
        vl_cofins = r.vl_cofins or 0
        carga_trib = (vl_icms + vl_pis + vl_cofins) / valor * 100 if valor > 0 else 0

        rows_intel.append({
            "Código":         p.cod_item,
            "Descrição":      p.descricao_padrao or p.descr_item,
            "Marca":          mrc_nomes.get(p.marca_id, "—") if p.marca_id else "—",
            "Grupo":          grp_nomes.get(p.grupo_id, "—") if p.grupo_id else "—",
            "Qtd. comprada":  qtd,
            "Valor total (R$)": valor,
            "Preço médio (R$)": preco_medio,
            "Nº notas":       r.n_notas,
            "Fornecedores":   forn_map.get(r.cod_item, 0),
            "ICMS (R$)":      vl_icms,
            "PIS+COFINS (R$)": vl_pis + vl_cofins,
            "Carga trib. (%)": carga_trib,
        })

    if not rows_intel:
        st.info("Nenhum item fiscal encontrado para este cliente. Importe arquivos EFD para ver a inteligência de produtos.")
        st.stop()

    df_intel = pd.DataFrame(rows_intel).sort_values("Valor total (R$)", ascending=False)

    # Filtros
    if1, if2, if3 = st.columns([3, 2, 2])
    busca_int  = if1.text_input("Buscar produto", placeholder="Descrição ou código...", key="busca_int")
    grp_intel  = if2.selectbox(
        "Grupo",
        ["Todos"] + sorted({r["Grupo"] for r in rows_intel if r["Grupo"] != "—"}),
        key="grp_intel",
    )
    mrc_intel  = if3.selectbox(
        "Marca",
        ["Todos"] + sorted({r["Marca"] for r in rows_intel if r["Marca"] != "—"}),
        key="mrc_intel",
    )

    df_f = df_intel.copy()
    if busca_int:
        t = busca_int.lower()
        df_f = df_f[df_f["Descrição"].str.lower().str.contains(t) | df_f["Código"].str.lower().str.contains(t)]
    if grp_intel != "Todos":
        df_f = df_f[df_f["Grupo"] == grp_intel]
    if mrc_intel != "Todos":
        df_f = df_f[df_f["Marca"] == mrc_intel]

    st.caption(f"{len(df_f)} produto(s) — ordenados por valor total de compras")

    # Cards de resumo
    ci1, ci2, ci3, ci4 = st.columns(4)
    ci1.metric("Valor total comprado",   f"R$ {df_f['Valor total (R$)'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    ci2.metric("Carga tributária média", f"{df_f['Carga trib. (%)'].mean():.1f}%")
    ci3.metric("Produtos com 1 fornecedor",
               str(len(df_f[df_f["Fornecedores"] == 1])),
               help="Risco de concentração — compra exclusiva de um único fornecedor")
    ci4.metric("Itens sem classificação",
               str(len([p for p in produtos if not p.categoria_id])))

    st.dataframe(
        df_f,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor total (R$)":   st.column_config.NumberColumn(format="R$ %.2f"),
            "Preço médio (R$)":   st.column_config.NumberColumn(format="R$ %.2f"),
            "ICMS (R$)":          st.column_config.NumberColumn(format="R$ %.2f"),
            "PIS+COFINS (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
            "Carga trib. (%)":    st.column_config.NumberColumn(format="%.1f%%"),
            "Qtd. comprada":      st.column_config.NumberColumn(format="%.2f"),
            "Fornecedores":       st.column_config.NumberColumn(format="%d"),
            "Nº notas":           st.column_config.NumberColumn(format="%d"),
        },
    )
