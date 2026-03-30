from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Participante(Base):
    __tablename__ = "participantes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    cod_part = Column(String, nullable=False)
    nome = Column(String)
    cod_pais = Column(String(5))
    cnpj = Column(String(14))
    cpf = Column(String(11))
    ie = Column(String)
    cod_mun = Column(String(7))
    suframa = Column(String)
    endereco = Column(String)
    num = Column(String)
    compl = Column(String)
    bairro = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'cod_part', name='uq_tenant_participante'),
    )

    tenant = relationship("Tenant", back_populates="participantes")
