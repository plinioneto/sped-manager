import re
from sqlalchemy import func, case
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.repositories.base_repo import BaseRepository


def _normalizar_cnpj(valor: str) -> str:
    """Remove pontuação do CNPJ digitado para bater com o banco (sem máscara)."""
    return re.sub(r"\D", "", valor)


class ComprasRepository(BaseRepository):

    def metricas_globais(self) -> dict:
        base = self.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.tenant_id == self.tenant_id,
            DocumentoFiscal.ind_oper == "0",
        )

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

        total_itens_comprados = (
            self.session.query(func.count(ItemFiscal.id))
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
            .scalar() or 0
        )

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

    def listar_notas(
        self,
        mes: str = None,
        fornecedor: str = None,
        num_nota: str = None,
        produto: str = None,
    ) -> list:
        q = self.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.tenant_id == self.tenant_id,
            DocumentoFiscal.ind_oper == "0",
        )
        if mes:
            q = q.filter(func.strftime("%Y%m", DocumentoFiscal.dt_doc) == mes)
        if fornecedor:
            q = q.filter(DocumentoFiscal.cod_part.ilike(f"%{_normalizar_cnpj(fornecedor)}%"))
        if num_nota:
            q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
        if produto:
            termo = f"%{produto}%"
            subq = (
                self.session.query(ItemFiscal.documento_id)
                .outerjoin(
                    Produto,
                    (Produto.tenant_id == self.tenant_id)
                    & (Produto.cod_item == ItemFiscal.cod_item),
                )
                .filter(
                    ItemFiscal.tenant_id == self.tenant_id,
                    ItemFiscal.cod_item.ilike(termo) | Produto.descr_item.ilike(termo),
                )
                .subquery()
            )
            q = q.filter(DocumentoFiscal.id.in_(subq))
        return q.order_by(DocumentoFiscal.dt_doc.desc()).all()

    def listar_itens(
        self,
        mes: str = None,
        fornecedor: str = None,
        num_nota: str = None,
        produto: str = None,
    ) -> list:
        q = (
            self.session.query(ItemFiscal, DocumentoFiscal, Produto)
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
        if mes:
            q = q.filter(func.strftime("%Y%m", DocumentoFiscal.dt_doc) == mes)
        if fornecedor:
            q = q.filter(DocumentoFiscal.cod_part.ilike(f"%{_normalizar_cnpj(fornecedor)}%"))
        if num_nota:
            q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
        if produto:
            termo = f"%{produto}%"
            q = q.filter(
                ItemFiscal.cod_item.ilike(termo)
                | ItemFiscal.descr_compl.ilike(termo)
                | Produto.descr_item.ilike(termo)
            )
        return q.order_by(DocumentoFiscal.dt_doc.desc(), ItemFiscal.num_item).all()

    def agrupar_por_fornecedor(
        self,
        mes: str = None,
        fornecedor: str = None,
        num_nota: str = None,
        produto: str = None,
    ) -> list:
        q = (
            self.session.query(
                DocumentoFiscal.cod_part,
                func.count(DocumentoFiscal.id.distinct()).label("qtd_notas"),
                func.sum(DocumentoFiscal.vl_doc).label("total_compras"),
                func.sum(DocumentoFiscal.vl_icms).label("total_icms"),
                func.sum(DocumentoFiscal.vl_pis).label("total_pis"),
                func.sum(DocumentoFiscal.vl_cofins).label("total_cofins"),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        if mes:
            q = q.filter(func.strftime("%Y%m", DocumentoFiscal.dt_doc) == mes)
        if fornecedor:
            q = q.filter(DocumentoFiscal.cod_part.ilike(f"%{_normalizar_cnpj(fornecedor)}%"))
        if num_nota:
            q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
        if produto:
            termo = f"%{produto}%"
            subq = (
                self.session.query(ItemFiscal.documento_id)
                .outerjoin(
                    Produto,
                    (Produto.tenant_id == self.tenant_id)
                    & (Produto.cod_item == ItemFiscal.cod_item),
                )
                .filter(
                    ItemFiscal.tenant_id == self.tenant_id,
                    ItemFiscal.cod_item.ilike(termo) | Produto.descr_item.ilike(termo),
                )
                .subquery()
            )
            q = q.filter(DocumentoFiscal.id.in_(subq))
        return (
            q.group_by(DocumentoFiscal.cod_part)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .all()
        )

    def agrupar_por_produto(
        self,
        mes: str = None,
        fornecedor: str = None,
        num_nota: str = None,
        produto: str = None,
    ) -> list:
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
        if mes:
            q = q.filter(func.strftime("%Y%m", DocumentoFiscal.dt_doc) == mes)
        if fornecedor:
            q = q.filter(DocumentoFiscal.cod_part.ilike(f"%{_normalizar_cnpj(fornecedor)}%"))
        if num_nota:
            q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
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
