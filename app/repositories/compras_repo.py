import re
from sqlalchemy import func, case
from app.models.documento_fiscal import DocumentoFiscal
from app.utils.sql_compat import sf_yearmonth, sf_year, sf_month
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.models.participante import Participante
from app.models.categoria import Departamento, Grupo, Categoria
from app.models.marca import Marca
from app.models.fabricante import Fabricante
from app.repositories.base_repo import BaseRepository


def _normalizar_cnpj(valor: str) -> str:
    """Remove pontuação do CNPJ digitado para bater com o banco (sem máscara)."""
    return re.sub(r"\D", "", valor)


def _aplicar_filtros_doc(q, session, tenant_id, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None):
    """Aplica os 4 filtros padrão a uma query que já contém DocumentoFiscal."""
    if ano:
        q = q.filter(sf_year(DocumentoFiscal.dt_doc) == ano)
    if meses:
        q = q.filter(sf_month(DocumentoFiscal.dt_doc).in_(meses))
    if fornecedor:
        cnpj_norm = _normalizar_cnpj(fornecedor)
        termo = f"%{fornecedor}%"
        subq_part = (
            session.query(Participante.cod_part)
            .filter(Participante.tenant_id == tenant_id)
        )
        if cnpj_norm:
            subq_part = subq_part.filter(
                Participante.nome.ilike(termo)
                | Participante.cnpj.ilike(f"%{cnpj_norm}%"),
            )
        else:
            subq_part = subq_part.filter(Participante.nome.ilike(termo))
        subq_part = subq_part.subquery().select()

        if cnpj_norm:
            q = q.filter(
                DocumentoFiscal.cod_part.ilike(f"%{cnpj_norm}%")
                | DocumentoFiscal.cod_part.in_(subq_part)
            )
        else:
            q = q.filter(DocumentoFiscal.cod_part.in_(subq_part))
    if num_nota:
        q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
    if produto:
        termo = f"%{produto}%"
        subq = (
            session.query(ItemFiscal.documento_id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(
                ItemFiscal.tenant_id == tenant_id,
                ItemFiscal.cod_item.ilike(termo) | Produto.descr_item.ilike(termo),
            )
            .subquery()
        )
        q = q.filter(DocumentoFiscal.id.in_(subq))
    return q


class ComprasRepository(BaseRepository):

    def _base_entrada(self):
        """Query base: DocumentoFiscal de entrada filtrado por tenant."""
        return self.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.tenant_id == self.tenant_id,
            DocumentoFiscal.ind_oper == "0",
        )

    def _filtrar(self, q, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None):
        return _aplicar_filtros_doc(q, self.session, self.tenant_id, ano, meses, fornecedor, num_nota, produto)

    # ------------------------------------------------------------------
    # Métricas
    # ------------------------------------------------------------------

    def metricas_globais(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> dict:
        base = self._filtrar(self._base_entrada(), ano, meses, fornecedor, num_nota, produto)

        total_notas = base.with_entities(
            func.count(DocumentoFiscal.id)
        ).scalar() or 0

        total_fornecedores = base.filter(
            DocumentoFiscal.cod_part.isnot(None)
        ).with_entities(
            func.count(DocumentoFiscal.cod_part.distinct())
        ).scalar() or 0

        valor_total_compras = base.with_entities(
            func.sum(DocumentoFiscal.vl_doc)
        ).scalar() or 0.0

        q_itens = (
            self.session.query(func.count(ItemFiscal.id))
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q_itens = self._filtrar(q_itens, ano, meses, fornecedor, num_nota, produto)
        total_itens_comprados = q_itens.scalar() or 0

        return {
            "total_notas": total_notas,
            "total_fornecedores": total_fornecedores,
            "valor_total_compras": valor_total_compras,
            "total_itens_comprados": total_itens_comprados,
        }

    def meses_disponiveis(self) -> list:
        rows = (
            self.session.query(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes")
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
            .distinct()
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc).desc())
            .all()
        )
        return [r.mes for r in rows if r.mes]

    # ------------------------------------------------------------------
    # Listagens detalhadas
    # ------------------------------------------------------------------

    def listar_notas(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        q = (
            self.session.query(DocumentoFiscal, Participante.nome.label("nome_part"))
            .outerjoin(
                Participante,
                (Participante.tenant_id == self.tenant_id)
                & (Participante.cod_part == DocumentoFiscal.cod_part),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return q.order_by(DocumentoFiscal.dt_doc.desc()).all()

    def listar_itens(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        q = (
            self.session.query(ItemFiscal, DocumentoFiscal, Produto, Participante.nome.label("nome_part"))
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(
                Participante,
                (Participante.tenant_id == self.tenant_id)
                & (Participante.cod_part == DocumentoFiscal.cod_part),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto=None)
        if produto:
            termo = f"%{produto}%"
            q = q.filter(
                ItemFiscal.cod_item.ilike(termo)
                | ItemFiscal.descr_compl.ilike(termo)
                | Produto.descr_item.ilike(termo)
            )
        return q.order_by(DocumentoFiscal.dt_doc.desc(), ItemFiscal.num_item).all()

    # ------------------------------------------------------------------
    # Agrupamentos
    # ------------------------------------------------------------------

    def agrupar_por_fornecedor(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None,
                               departamento_id=None, grupo_id=None, categoria_id=None) -> list:
        q = (
            self.session.query(
                DocumentoFiscal.cod_part,
                Participante.nome.label("nome_part"),
                Participante.cnpj.label("cnpj_part"),
                func.count(DocumentoFiscal.id.distinct()).label("qtd_notas"),
                func.sum(DocumentoFiscal.vl_doc).label("total_compras"),
                func.sum(DocumentoFiscal.vl_icms).label("total_icms"),
                func.sum(DocumentoFiscal.vl_pis).label("total_pis"),
                func.sum(DocumentoFiscal.vl_cofins).label("total_cofins"),
            )
            .outerjoin(
                Participante,
                (Participante.tenant_id == self.tenant_id)
                & (Participante.cod_part == DocumentoFiscal.cod_part),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        q = self._filtro_hierarquia_via_doc(q, departamento_id, grupo_id, categoria_id)
        return (
            q.group_by(DocumentoFiscal.cod_part, Participante.nome, Participante.cnpj)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .all()
        )

    def agrupar_por_produto(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                Produto.unid_inv,
                func.sum(ItemFiscal.qtd).label("qtd_total"),
                func.sum(ItemFiscal.vl_item).label("vl_total"),
                func.avg(
                    case(
                        (ItemFiscal.qtd != 0, ItemFiscal.vl_item / ItemFiscal.qtd),
                        else_=None,
                    )
                ).label("preco_medio"),
                func.count(DocumentoFiscal.id.distinct()).label("qtd_notas"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto=None)
        if produto:
            termo = f"%{produto}%"
            q = q.filter(
                ItemFiscal.cod_item.ilike(termo) | Produto.descr_item.ilike(termo)
            )
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item, Produto.unid_inv)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Novas queries para gráficos
    # ------------------------------------------------------------------

    def evolucao_mensal(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Agrupa compras por mês: valor, notas, ticket médio."""
        q = (
            self.session.query(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
                func.count(DocumentoFiscal.id).label("total_notas"),
                func.sum(DocumentoFiscal.vl_doc).label("valor_total"),
                func.avg(DocumentoFiscal.vl_doc).label("ticket_medio"),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )

    def top_fornecedores_evolucao(self, limit=5, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Série temporal mensal dos top N fornecedores por valor."""
        top_q = (
            self.session.query(DocumentoFiscal.cod_part)
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                DocumentoFiscal.cod_part.isnot(None),
            )
        )
        top_q = self._filtrar(top_q, ano, meses, fornecedor, num_nota, produto)
        top_fornecedores = [
            r[0] for r in top_q.group_by(DocumentoFiscal.cod_part)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .limit(limit)
            .all()
        ]
        if not top_fornecedores:
            return []

        q = (
            self.session.query(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
                DocumentoFiscal.cod_part,
                Participante.nome.label("nome_part"),
                func.sum(DocumentoFiscal.vl_doc).label("valor_total"),
            )
            .outerjoin(
                Participante,
                (Participante.tenant_id == self.tenant_id)
                & (Participante.cod_part == DocumentoFiscal.cod_part),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                DocumentoFiscal.cod_part.in_(top_fornecedores),
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(
                sf_yearmonth(DocumentoFiscal.dt_doc),
                DocumentoFiscal.cod_part,
                Participante.nome,
            )
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )

    # ------------------------------------------------------------------
    # Agrupamento por classificação mercadológica
    # ------------------------------------------------------------------

    def _base_itens_entrada(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None):
        """Base compartilhada para queries de agrupamento hierárquico."""
        q = (
            self.session.query(
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        return self._filtrar(q, ano, meses, fornecedor, num_nota, produto)

    def agrupar_por_departamento(self, ano=None, meses=None, fornecedor=None,
                                  num_nota=None, produto=None) -> list:
        """Valor de compras agrupado por departamento (inclui Não classificado)."""
        q = (
            self.session.query(
                func.coalesce(Departamento.descricao, "Não classificado").label("nome"),
                Produto.departamento_id,
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Departamento, Departamento.id == Produto.departamento_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(
                func.coalesce(Departamento.descricao, "Não classificado"),
                Produto.departamento_id,
            )
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def agrupar_por_grupo(self, departamento_id, ano=None, meses=None, fornecedor=None,
                           num_nota=None, produto=None) -> list:
        """Valor de compras agrupado por grupo, filtrado por departamento."""
        q = (
            self.session.query(
                func.coalesce(Grupo.descricao, "Não classificado").label("nome"),
                Produto.grupo_id,
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Grupo, Grupo.id == Produto.grupo_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                Produto.departamento_id == departamento_id,
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(
                func.coalesce(Grupo.descricao, "Não classificado"),
                Produto.grupo_id,
            )
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def agrupar_por_categoria(self, grupo_id, ano=None, meses=None, fornecedor=None,
                               num_nota=None, produto=None) -> list:
        """Valor de compras agrupado por categoria, filtrado por grupo."""
        q = (
            self.session.query(
                func.coalesce(Categoria.descricao, "Não classificado").label("nome"),
                Produto.categoria_id,
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Categoria, Categoria.id == Produto.categoria_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                Produto.grupo_id == grupo_id,
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(
                func.coalesce(Categoria.descricao, "Não classificado"),
                Produto.categoria_id,
            )
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def agrupar_por_produto_categoria(self, categoria_id, ano=None, meses=None,
                                       fornecedor=None, num_nota=None, produto=None) -> list:
        """Produtos de uma categoria específica com valores de compra."""
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                Produto.descricao_padrao,
                Produto.unid_inv,
                func.sum(ItemFiscal.vl_item).label("vl_total"),
                func.sum(ItemFiscal.qtd).label("qtd_total"),
                func.count(DocumentoFiscal.id.distinct()).label("qtd_notas"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                Produto.categoria_id == categoria_id,
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item, Produto.descricao_padrao, Produto.unid_inv)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def agrupar_por_fabricante(self, departamento_id=None, grupo_id=None, categoria_id=None,
                               ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Valor de compras agrupado por fabricante, com filtro hierárquico opcional."""
        q = (
            self.session.query(
                func.coalesce(Fabricante.nome, "Sem fabricante").label("nome"),
                Marca.fabricante_id,
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Marca, Marca.id == Produto.marca_id)
            .outerjoin(Fabricante, Fabricante.id == Marca.fabricante_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        q = self._filtro_hierarquia_por_produto(q, departamento_id, grupo_id, categoria_id)
        return (
            q.group_by(
                func.coalesce(Fabricante.nome, "Sem fabricante"),
                Marca.fabricante_id,
            )
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def agrupar_por_marca(self, fabricante_id=None, departamento_id=None, grupo_id=None, categoria_id=None,
                          ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Valor de compras agrupado por marca, com filtro por fabricante e hierarquia opcionais."""
        q = (
            self.session.query(
                func.coalesce(Marca.nome, "Sem marca").label("nome"),
                Produto.marca_id,
                func.coalesce(Fabricante.nome, "Sem fabricante").label("fabricante_nome"),
                func.sum(ItemFiscal.vl_item).label("valor"),
                func.count(ItemFiscal.id).label("qtd_itens"),
                func.count(ItemFiscal.cod_item.distinct()).label("qtd_skus"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Marca, Marca.id == Produto.marca_id)
            .outerjoin(Fabricante, Fabricante.id == Marca.fabricante_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        q = self._filtro_hierarquia_por_produto(q, departamento_id, grupo_id, categoria_id)
        if fabricante_id is not None:
            q = q.filter(Marca.fabricante_id == fabricante_id)
        return (
            q.group_by(
                func.coalesce(Marca.nome, "Sem marca"),
                Produto.marca_id,
                func.coalesce(Fabricante.nome, "Sem fabricante"),
            )
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def distribuicao_cfop(self, ano=None, meses=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Agrupa itens de entrada por CFOP: valor e contagem."""
        q = (
            self.session.query(
                ItemFiscal.cfop,
                func.sum(ItemFiscal.vl_item).label("valor_total"),
                func.count(ItemFiscal.id).label("qtd_itens"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, ano, meses, fornecedor, num_nota, produto)
        return (
            q.group_by(ItemFiscal.cfop)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )
