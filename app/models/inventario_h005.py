from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class InventarioH005(Base):
    __tablename__ = "inventarios_h005"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)

    dt_inv = Column(DateTime, nullable=False)
    vl_inv = Column(Float, default=0.0)
    mot_inv = Column(String(2))
    file_path = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)

    itens = relationship("InventarioH010", back_populates="inventario")

    __table_args__ = (
        UniqueConstraint("tenant_id", "dt_inv", "mot_inv", name="uq_inventario_h005"),
    )
