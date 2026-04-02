from datetime import datetime

from sqlalchemy import func, case

from app.models.estoque_k200 import EstoqueK200
from app.models.inventario_h005 import InventarioH005
from app.models.inventario_h010 import InventarioH010
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.repositories.base_repo import BaseRepository


class EstoqueVirtualRepository(BaseRepository):
    """
    Estoque virtual calculado a partir das movimentações de NF-e (C100/C170).

    Fórmula:
        Saldo = Estoque Inicial + Entradas - Saídas

    Prioridade do estoque inicial:
        1. K200 mais recente (Bloco K)
        2. H010 do inventário mais recente (Bloco H)
        3. Zero para todos os produtos (sem Bloco H ou K)
    """

    # ------------------------------------------------------------------
    # Estoque inicial
    # ------------------------------------------------------------------

    def fonte_estoque_inicial(self) -> dict:
        """
        Determina a fonte e os valores do estoque inicial.

        Retorna dict com:
            fonte     : 'k200' | 'h010' | 'zero'
            data_base : date | None  (movimentações a partir desta data)
            estoque   : {cod_item: qty}
        """
        # 1. Tenta K200
        dt_k200 = (
            self.session.query(func.max(EstoqueK200.dt_est))
            .filter(EstoqueK200.tenant_id == self.tenant_id)
            .scalar()
        )
        if dt_k200 is not None:
            rows = (
                self.session.query(
                    EstoqueK200.cod_item,
                    func.sum(EstoqueK200.qt_est).label("qt_total"),
                )
                .filter(
                    EstoqueK200.tenant_id == self.tenant_id,
                    EstoqueK200.dt_est == dt_k200,
                )
                .group_by(EstoqueK200.cod_item)
                .all()
            )
            return {
                "fonte": "k200",
                "data_base": dt_k200.date() if hasattr(dt_k200, "date") else dt_k200,
                "estoque": {r.cod_item: r.qt_total or 0.0 for r in rows},
            }

        # 2. Tenta H010 via H005 mais recente
        h005 = (
            self.session.query(InventarioH005)
            .filter(InventarioH005.tenant_id == self.tenant_id)
            .order_by(InventarioH005.dt_inv.desc())
            .first()
        )
        if h005 is not None:
            rows = (
                self.session.query(
                    InventarioH010.cod_item,
                    func.sum(InventarioH010.qtd).label("qt_total"),
                )
                .filter(
                    InventarioH010.tenant_id == self.tenant_id,
                    InventarioH010.inventario_id == h005.id,
                )
                .group_by(InventarioH010.cod_item)
                .all()
            )
            return {
                "fonte": "h010",
                "data_base": h005.dt_inv.date() if hasattr(h005.dt_inv, "date") else h005.dt_inv,
                "estoque": {r.cod_item: r.qt_total or 0.0 for r in rows},
            }

        # 3. Sem base — parte do zero
        return {"fonte": "zero", "data_base": None, "estoque": {}}

    # ------------------------------------------------------------------
    # Movimentação
    # ------------------------------------------------------------------

    def movimentacao_por_produto(self, data_base) -> list:
        """
        Retorna entradas e saídas por produto a partir de data_base.

        Parâmetros:
            data_base : date | None  (None = toda a história)

        Retorna lista de Row com:
            cod_item, descr_item, unid, qt_entradas, qt_saidas
        """
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                Produto.unid_inv.label("unid"),
                func.sum(
                    case((DocumentoFiscal.ind_oper == "0", ItemFiscal.qtd), else_=0.0)
                ).label("qt_entradas"),
                func.sum(
                    case((DocumentoFiscal.ind_oper == "1", ItemFiscal.qtd), else_=0.0)
                ).label("qt_saidas"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper.in_(["0", "1"]),
            )
        )

        if data_base is not None:
            data_base_dt = datetime.combine(data_base, datetime.min.time())
            q = q.filter(DocumentoFiscal.dt_doc >= data_base_dt)

        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item, Produto.unid_inv)
            .order_by(ItemFiscal.cod_item)
            .all()
        )

    # ------------------------------------------------------------------
    # Saldo virtual
    # ------------------------------------------------------------------

    def saldo_virtual(self, busca: str = None) -> list:
        """
        Combina estoque inicial + movimentações e retorna saldo por produto.

        Parâmetros:
            busca : str | None  (filtra por código ou descrição)

        Retorna lista de dicts com:
            cod_item, descr_item, unid,
            qt_inicial, qt_entradas, qt_saidas, qt_atual
        """
        fonte_info = self.fonte_estoque_inicial()
        movs = self.movimentacao_por_produto(fonte_info["data_base"])
        estoque_ini = fonte_info["estoque"]

        todos_codigos = {r.cod_item for r in movs} | set(estoque_ini.keys())
        mov_idx = {r.cod_item: r for r in movs}

        resultado = []
        for cod in sorted(todos_codigos):
            mov = mov_idx.get(cod)
            qt_ini = estoque_ini.get(cod, 0.0)
            qt_ent = mov.qt_entradas if mov else 0.0
            qt_sai = mov.qt_saidas if mov else 0.0
            descr = mov.descr_item if mov else None
            unid = mov.unid if mov else None

            if busca:
                termo = busca.lower()
                if not (
                    termo in (cod or "").lower()
                    or termo in (descr or "").lower()
                ):
                    continue

            resultado.append(
                {
                    "cod_item": cod,
                    "descr_item": descr or "—",
                    "unid": unid or "—",
                    "qt_inicial": qt_ini,
                    "qt_entradas": qt_ent,
                    "qt_saidas": qt_sai,
                    "qt_atual": qt_ini + qt_ent - qt_sai,
                }
            )

        return resultado

    # ------------------------------------------------------------------
    # Métricas
    # ------------------------------------------------------------------

    def metricas_virtual(self) -> dict:
        """
        Retorna contagens resumidas do estoque virtual (sem filtro de busca).

        Retorna dict com:
            total_skus, skus_positivo, skus_negativo, skus_zerado
        """
        saldos = self.saldo_virtual()
        total = len(saldos)
        pos = sum(1 for s in saldos if s["qt_atual"] > 0)
        neg = sum(1 for s in saldos if s["qt_atual"] < 0)
        zero = sum(1 for s in saldos if s["qt_atual"] == 0)
        return {
            "total_skus": total,
            "skus_positivo": pos,
            "skus_negativo": neg,
            "skus_zerado": zero,
        }
