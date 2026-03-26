from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class IcmsC190(Base):
    __tablename__ = "icms_c190"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    chv_doc = Column(String(44), nullable=False)
    documento_id = Column(Integer, ForeignKey("documentos_fiscais.id"), nullable=True)

    cst_icms = Column(String(3))
    cfop = Column(String(4))
    aliq_icms = Column(String(10))   # string para evitar problema de precisão em constraint
    vl_opr = Column(Float, default=0.0)
    vl_bc_icms = Column(Float, default=0.0)
    vl_icms = Column(Float, default=0.0)
    vl_bc_icms_st = Column(Float, default=0.0)
    vl_icms_st = Column(Float, default=0.0)
    vl_red_bc = Column(Float, default=0.0)
    vl_pis = Column(Float, default=0.0)
    vl_cofins = Column(Float, default=0.0)
    cod_obs = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)

    documento = relationship("DocumentoFiscal", back_populates="icms_c190")

    __table_args__ = (
        UniqueConstraint("tenant_id", "chv_doc", "cst_icms", "cfop", "aliq_icms", name="uq_icms_c190"),
    )
