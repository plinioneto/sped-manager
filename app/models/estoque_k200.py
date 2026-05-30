from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from app.models.base import Base


class EstoqueK200(Base):
    __tablename__ = "estoques_k200"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)

    dt_est = Column(DateTime, nullable=False)
    cod_item = Column(String, nullable=False)
    qt_est = Column(Float, default=0.0)
    ind_est = Column(String(1))  # '0'=próprio, '1'=de terceiro, '2'=em poder de terceiro
    criado_em = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dt_est", "cod_item", "ind_est", name="uq_estoque_k200"),
    )
