from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    cod_item = Column(String, nullable=False)
    descr_item = Column(String, nullable=False)
    cod_barra = Column(String)
    cod_ant_item = Column(String)
    unid_inv = Column(String(6))
    tipo_item = Column(String)
    cod_ncm = Column(String(8))
    ex_ipi = Column(String)
    cod_gen = Column(String)
    cod_lst = Column(String)
    aliq_icms = Column(Float, default=0.0)
    cest = Column(String)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'cod_item', name='uq_tenant_produto'),
    )

    tenant = relationship("Tenant", back_populates="produtos")