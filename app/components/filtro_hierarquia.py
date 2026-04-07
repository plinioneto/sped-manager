import streamlit as st
from sqlalchemy.orm import Session
from app.models.categoria import Departamento, Grupo, Categoria


def render_filtro_hierarquia(session: Session, key_prefix: str = "hier") -> dict:
    """Renderiza filtros cascateados Departamento > Grupo > Categoria na sidebar.

    Retorna dict com departamento_id, grupo_id, categoria_id (None = todos).
    """
    deptos = (
        session.query(Departamento)
        .order_by(Departamento.descricao)
        .all()
    )
    opcoes_depto = {d.descricao: d.id for d in deptos}

    st.sidebar.markdown("**Filtro por Categoria**")

    depto_sel = st.sidebar.selectbox(
        "Departamento",
        options=["Todos"] + list(opcoes_depto.keys()),
        key=f"{key_prefix}_depto",
    )
    departamento_id = opcoes_depto.get(depto_sel)

    grupo_id = None
    categoria_id = None

    if departamento_id:
        grupos = (
            session.query(Grupo)
            .filter(Grupo.departamento_id == departamento_id)
            .order_by(Grupo.descricao)
            .all()
        )
        opcoes_grupo = {g.descricao: g.id for g in grupos}

        grupo_sel = st.sidebar.selectbox(
            "Grupo",
            options=["Todos"] + list(opcoes_grupo.keys()),
            key=f"{key_prefix}_grupo",
        )
        grupo_id = opcoes_grupo.get(grupo_sel)

        if grupo_id:
            categorias = (
                session.query(Categoria)
                .filter(Categoria.grupo_id == grupo_id)
                .order_by(Categoria.descricao)
                .all()
            )
            opcoes_cat = {c.descricao: c.id for c in categorias}

            cat_sel = st.sidebar.selectbox(
                "Categoria",
                options=["Todos"] + list(opcoes_cat.keys()),
                key=f"{key_prefix}_cat",
            )
            categoria_id = opcoes_cat.get(cat_sel)

    return {
        "departamento_id": departamento_id,
        "grupo_id": grupo_id,
        "categoria_id": categoria_id,
    }
