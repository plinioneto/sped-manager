from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from app.models.base import Base


class GoldKpisMensais(Base):
    __tablename__ = "gold_kpis_mensais"

    id        = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False, index=True)
    ano       = Column(Integer, nullable=False)
    mes       = Column(Integer, nullable=False)

    # Vendas (saídas — ind_oper=1)
    vl_faturamento  = Column(Numeric(15, 2), default=0)
    qtd_notas_saida = Column(Integer, default=0)
    ticket_medio    = Column(Numeric(15, 2), default=0)

    # Compras (entradas — ind_oper=0)
    vl_compras        = Column(Numeric(15, 2), default=0)
    qtd_notas_entrada = Column(Integer, default=0)

    # Fiscal
    vl_icms_debito  = Column(Numeric(15, 2), default=0)  # ICMS das saídas
    vl_icms_credito = Column(Numeric(15, 2), default=0)  # ICMS das entradas
    vl_icms_pagar   = Column(Numeric(15, 2), default=0)  # débito - crédito
    vl_icms_st      = Column(Numeric(15, 2), default=0)
    vl_pis          = Column(Numeric(15, 2), default=0)
    vl_cofins       = Column(Numeric(15, 2), default=0)

    atualizado_em = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "ano", "mes", name="uq_gold_kpis_tenant_ano_mes"),
    )
