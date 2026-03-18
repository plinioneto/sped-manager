from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
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
    vl_doc = Column(Float, default=0.0)
    vl_desc = Column(Float, default=0.0)
    vl_merc = Column(Float, default=0.0)
    vl_bc_icms = Column(Float, default=0.0)
    vl_icms = Column(Float, default=0.0)
    vl_bc_icms_st = Column(Float, default=0.0)
    vl_icms_st = Column(Float, default=0.0)
    vl_pis = Column(Float, default=0.0)
    vl_cofins = Column(Float, default=0.0)
    criado_em = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="documentos_fiscais")
    itens = relationship("ItemFiscal", back_populates="documento")