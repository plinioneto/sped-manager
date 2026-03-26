from sqlalchemy import func
from app.models.estoque_k200 import EstoqueK200
from app.models.produto import Produto
from app.repositories.base_repo import BaseRepository


class EstoqueRepository(BaseRepository):

    def datas_disponiveis(self):
        return (
            self.session.query(EstoqueK200.dt_est)
            .filter(EstoqueK200.tenant_id == self.tenant_id)
            .distinct()
            .order_by(EstoqueK200.dt_est.desc())
            .all()
        )

    def saldo_por_data(self, dt_est, busca: str = None):
        q = (
            self.session.query(EstoqueK200, Produto)
            .outerjoin(Produto, (
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == EstoqueK200.cod_item,
            ))
            .filter(
                EstoqueK200.tenant_id == self.tenant_id,
                EstoqueK200.dt_est == dt_est,
            )
        )
        if busca:
            termo = f"%{busca}%"
            q = q.filter(
                (EstoqueK200.cod_item.ilike(termo)) |
                (Produto.descr_item.ilike(termo))
            )
        return q.order_by(EstoqueK200.cod_item).all()

    def saldo_mais_recente(self, busca: str = None):
        subq = (
            self.session.query(
                EstoqueK200.cod_item,
                EstoqueK200.ind_est,
                func.max(EstoqueK200.dt_est).label("dt_max"),
            )
            .filter(EstoqueK200.tenant_id == self.tenant_id)
            .group_by(EstoqueK200.cod_item, EstoqueK200.ind_est)
            .subquery()
        )
        q = (
            self.session.query(EstoqueK200, Produto)
            .outerjoin(Produto, (
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == EstoqueK200.cod_item,
            ))
            .join(subq, (
                (EstoqueK200.cod_item == subq.c.cod_item) &
                (EstoqueK200.ind_est == subq.c.ind_est) &
                (EstoqueK200.dt_est == subq.c.dt_max)
            ))
            .filter(EstoqueK200.tenant_id == self.tenant_id)
        )
        if busca:
            termo = f"%{busca}%"
            q = q.filter(
                (EstoqueK200.cod_item.ilike(termo)) |
                (Produto.descr_item.ilike(termo))
            )
        return q.order_by(EstoqueK200.cod_item).all()

    def metricas_k200(self, dt_est=None):
        q = self.session.query(EstoqueK200).filter(
            EstoqueK200.tenant_id == self.tenant_id,
        )
        if dt_est:
            q = q.filter(EstoqueK200.dt_est == dt_est)

        total_itens = q.filter(EstoqueK200.qt_est > 0).with_entities(
            func.count(EstoqueK200.id)
        ).scalar() or 0

        total_unidades = q.with_entities(
            func.sum(EstoqueK200.qt_est)
        ).scalar() or 0.0

        return {"total_itens": total_itens, "total_unidades": total_unidades}
