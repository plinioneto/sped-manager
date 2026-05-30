from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class InventarioH010(Base):
    __tablename__ = "inventarios_h010"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)
    inventario_id = Column(Integer, ForeignKey("inventarios_h005.id"), nullable=True)
    dt_inv = Column(DateTime, nullable=False)  # desnormalizado do H005 pai

    cod_item = Column(String, nullable=False)
    unid = Column(String(6))
    qtd = Column(Float, default=0.0)
    vl_unit = Column(Float, default=0.0)
    vl_item = Column(Float, default=0.0)
    ind_prop = Column(String(1))  # '0'=próprio, '1'=de terceiro
    cod_part = Column(String)
    txt_compl = Column(String)
    cod_cta = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)

    inventario = relationship("InventarioH005", back_populates="itens")

    __table_args__ = (
        UniqueConstraint("tenant_id", "dt_inv", "cod_item", "ind_prop", name="uq_inventario_h010"),
    )
