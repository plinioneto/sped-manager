import re
from sqlalchemy import func, case
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.models.participante import Participante
from app.repositories.base_repo import BaseRepository


def _normalizar_cnpj(valor: str) -> str:
    """Remove pontuação do CNPJ digitado para bater com o banco (sem máscara)."""
    return re.sub(r"\D", "", valor)


def _aplicar_filtros_doc(q, session, tenant_id, mes=None, fornecedor=None, num_nota=None, produto=None):
    """Aplica os 4 filtros padrão a uma query que já contém DocumentoFiscal."""
    if mes:
        q = q.filter(func.strftime("%Y%m", DocumentoFiscal.dt_doc) == mes)
    if fornecedor:
        cnpj_norm = _normalizar_cnpj(fornecedor)
        termo = f"%{fornecedor}%"
        subq_part = (
            session.query(Participante.cod_part)
            .filter(
                Participante.tenant_id == tenant_id,
                Participante.nome.ilike(termo)
                | Participante.cnpj.ilike(f"%{cnpj_norm}%"),
            )
            .subquery()
        )
        q = q.filter(
            DocumentoFiscal.cod_part.ilike(f"%{cnpj_norm}%")
            | DocumentoFiscal.cod_part.in_(subq_part)
        )
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

    def _filtrar(self, q, mes=None, fornecedor=None, num_nota=None, produto=None):
        return _aplicar_filtros_doc(q, self.session, self.tenant_id, mes, fornecedor, num_nota, produto)

    # ------------------------------------------------------------------
    # Métricas
    # ------------------------------------------------------------------

    def metricas_globais(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> dict:
        base = self._filtrar(self._base_entrada(), mes, fornecedor, num_nota, produto)

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
        q_itens = self._filtrar(q_itens, mes, fornecedor, num_nota, produto)
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
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes")
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
            .distinct()
            .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc).desc())
            .all()
        )
        return [r.mes for r in rows if r.mes]

    # ------------------------------------------------------------------
    # Listagens detalhadas
    # ------------------------------------------------------------------

    def listar_notas(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto)
        return q.order_by(DocumentoFiscal.dt_doc.desc()).all()

    def listar_itens(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto=None)
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

    def agrupar_por_fornecedor(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto)
        return (
            q.group_by(DocumentoFiscal.cod_part, Participante.nome, Participante.cnpj)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .all()
        )

    def agrupar_por_produto(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto=None)
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

    def evolucao_mensal(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Agrupa compras por mês: valor, notas, ticket médio."""
        q = (
            self.session.query(
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
                func.count(DocumentoFiscal.id).label("total_notas"),
                func.sum(DocumentoFiscal.vl_doc).label("valor_total"),
                func.avg(DocumentoFiscal.vl_doc).label("ticket_medio"),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        q = self._filtrar(q, mes, fornecedor, num_nota, produto)
        return (
            q.group_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
            .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
            .all()
        )

    def top_fornecedores_evolucao(self, limit=5, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
        """Série temporal mensal dos top N fornecedores por valor."""
        top_q = (
            self.session.query(DocumentoFiscal.cod_part)
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                DocumentoFiscal.cod_part.isnot(None),
            )
        )
        top_q = self._filtrar(top_q, mes, fornecedor, num_nota, produto)
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
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto)
        return (
            q.group_by(
                func.strftime("%Y%m", DocumentoFiscal.dt_doc),
                DocumentoFiscal.cod_part,
                Participante.nome,
            )
            .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
            .all()
        )

    def distribuicao_cfop(self, mes=None, fornecedor=None, num_nota=None, produto=None) -> list:
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
        q = self._filtrar(q, mes, fornecedor, num_nota, produto)
        return (
            q.group_by(ItemFiscal.cfop)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )
