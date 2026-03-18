from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    codigo = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    ncm = Column(String(8))
    unidade = Column(String(6))
    preco_custo = Column(Float, default=0.0)
    preco_venda = Column(Float, default=0.0)
    estoque_atual = Column(Float, default=0.0)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="produtos")