from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy import Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class DocumentoFiscal(Base):
    __tablename__ = "documentos_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    chv_nfe = Column(String(44))
    ind_oper = Column(String)       # 0=entrada, 1=saída
    ind_emit = Column(String)
    cod_part = Column(String)
    cod_mod = Column(String)
    cod_sit = Column(String)
    ser = Column(String)
    num_doc = Column(String)
    dt_doc = Column(DateTime)
    dt_e_s = Column(DateTime)
    vl_doc = Column(Numeric(15, 2), default=0.0)
    vl_desc = Column(Numeric(15, 2), default=0.0)
    vl_merc = Column(Numeric(15, 2), default=0.0)
    vl_bc_icms = Column(Numeric(15, 2), default=0.0)
    vl_icms = Column(Numeric(15, 2), default=0.0)
    vl_bc_icms_st = Column(Numeric(15, 2), default=0.0)
    vl_icms_st = Column(Numeric(15, 2), default=0.0)
    vl_pis = Column(Numeric(15, 2), default=0.0)
    vl_cofins = Column(Numeric(15, 2), default=0.0)
    fonte = Column(String(3), default='efd')  # 'efd' | 'xml'
    criado_em = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="documentos_fiscais")
    itens = relationship("ItemFiscal", back_populates="documento")
    icms_c190 = relationship("IcmsC190", back_populates="documento")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'chv_nfe', name='uq_documento_tenant_chave'),
    )
