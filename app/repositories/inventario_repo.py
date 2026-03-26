from sqlalchemy import func
from app.models.inventario_h005 import InventarioH005
from app.models.inventario_h010 import InventarioH010
from app.models.produto import Produto
from app.repositories.base_repo import BaseRepository


class InventarioRepository(BaseRepository):

    def listar_inventarios(self):
        return (
            self.session.query(InventarioH005)
            .filter(InventarioH005.tenant_id == self.tenant_id)
            .order_by(InventarioH005.dt_inv.desc())
            .all()
        )

    def listar_itens(self, inventario_id: int):
        return (
            self.session.query(InventarioH010, Produto)
            .outerjoin(Produto, (
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == InventarioH010.cod_item,
            ))
            .filter(
                InventarioH010.tenant_id == self.tenant_id,
                InventarioH010.inventario_id == inventario_id,
            )
            .all()
        )

    def datas_disponiveis(self):
        return (
            self.session.query(
                InventarioH005.id,
                InventarioH005.dt_inv,
                InventarioH005.mot_inv,
                InventarioH005.vl_inv,
            )
            .filter(InventarioH005.tenant_id == self.tenant_id)
            .order_by(InventarioH005.dt_inv.desc())
            .all()
        )

    def total_itens(self, inventario_id: int) -> int:
        return (
            self.session.query(func.count(InventarioH010.id))
            .filter(
                InventarioH010.tenant_id == self.tenant_id,
                InventarioH010.inventario_id == inventario_id,
            )
            .scalar() or 0
        )
