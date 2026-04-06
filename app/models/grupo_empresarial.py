from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class GrupoEmpresarial(Base):
    __tablename__ = "grupos_empresariais"

    id        = Column(Integer, primary_key=True, index=True)
    nome      = Column(String, nullable=False)
    ativo     = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    tenants = relationship("Tenant", back_populates="grupo")
