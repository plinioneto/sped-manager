from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class DocumentoFiscal(Base):
    __tablename__ = "documentos_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    numero = Column(String, nullable=False)
    serie = Column(String)
    tipo = Column(String)        # entrada, saida
    chave_nfe = Column(String(44))
    cnpj_emitente = Column(String(18))
    cnpj_destinatario = Column(String(18))
    valor_total = Column(Float, default=0.0)
    valor_icms = Column(Float, default=0.0)
    valor_pis = Column(Float, default=0.0)
    valor_cofins = Column(Float, default=0.0)
    data_emissao = Column(DateTime)
    criado_em = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="documentos_fiscais")