from sqlalchemy.orm import Session
from app.models.produto import Produto
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.documento_fiscal import DocumentoFiscal


class BaseRepository:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def _filtro_hierarquia_por_produto(self, q, departamento_id=None, grupo_id=None, categoria_id=None):
        """Aplica filtro de hierarquia a query que JA contém Produto no JOIN."""
        if categoria_id:
            q = q.filter(Produto.categoria_id == categoria_id)
        elif grupo_id:
            q = q.filter(Produto.grupo_id == grupo_id)
        elif departamento_id:
            q = q.filter(Produto.departamento_id == departamento_id)
        return q

    def _filtro_hierarquia_via_item(self, q, departamento_id=None, grupo_id=None, categoria_id=None):
        """Aplica filtro de hierarquia a query com ItemFiscal, fazendo JOIN com Produto."""
        if not any([departamento_id, grupo_id, categoria_id]):
            return q
        q = q.join(
            Produto,
            (Produto.tenant_id == self.tenant_id)
            & (Produto.cod_item == ItemFiscal.cod_item),
        )
        return self._filtro_hierarquia_por_produto(q, departamento_id, grupo_id, categoria_id)

    def _filtro_hierarquia_via_doc(self, q, departamento_id=None, grupo_id=None, categoria_id=None):
        """Aplica filtro de hierarquia a query com DocumentoFiscal (sem ItemFiscal).
        Faz subquery: documento_ids que têm itens no departamento/grupo/categoria."""
        if not any([departamento_id, grupo_id, categoria_id]):
            return q
        subq = (
            self.session.query(ItemFiscal.documento_id)
            .join(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(ItemFiscal.tenant_id == self.tenant_id)
        )
        subq = self._filtro_hierarquia_por_produto(subq, departamento_id, grupo_id, categoria_id)
        q = q.filter(DocumentoFiscal.id.in_(subq.subquery().select()))
        return q