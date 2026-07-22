from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Consultor(Base):
    __tablename__ = "consultores"

    id             = Column(Integer, primary_key=True, index=True)
    nome           = Column(String, nullable=False)
    cnpj           = Column(String(14), nullable=True)
    telefone       = Column(String, nullable=True)
    logo_url       = Column(String, nullable=True)
    slogan         = Column(String, nullable=True)
    cor_primaria   = Column(String(7), default="#1d4ed8")
    cor_secundaria = Column(String(7), default="#1e40af")
    ativo          = Column(Boolean, default=True)
    criado_em      = Column(DateTime, default=datetime.utcnow)

    clientes = relationship("Tenant", back_populates="consultor")
