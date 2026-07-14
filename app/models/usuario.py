from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id         = Column(Integer, primary_key=True, index=True)
    tenant_id  = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    login      = Column(String, unique=True, nullable=False, index=True)
    senha_hash = Column(String, nullable=False)
    nome       = Column(String, nullable=False)
    role       = Column(String(10), nullable=False)  # 'admin' | 'cliente'
    ativo      = Column(Boolean, default=True)
    criado_em  = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
