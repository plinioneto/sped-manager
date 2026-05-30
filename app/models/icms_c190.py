from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy import Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class IcmsC190(Base):
    __tablename__ = "resumo_fiscal"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)
    chv_nfe = Column(String(44), nullable=False)
    documento_id = Column(Integer, ForeignKey("notas_fiscais.id"), nullable=True)

    cst_icms = Column(String(3))
    cfop = Column(String(4))
    aliq_icms = Column(Numeric(7, 4), default=0.0)
    vl_opr = Column(Numeric(15, 2), default=0.0)
    vl_bc_icms = Column(Numeric(15, 2), default=0.0)
    vl_icms = Column(Numeric(15, 2), default=0.0)
    vl_bc_icms_st = Column(Numeric(15, 2), default=0.0)
    vl_icms_st = Column(Numeric(15, 2), default=0.0)
    vl_red_bc = Column(Numeric(15, 2), default=0.0)
    vl_pis = Column(Numeric(15, 2), default=0.0)
    vl_cofins = Column(Numeric(15, 2), default=0.0)
    cod_obs = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)

    documento = relationship("DocumentoFiscal", back_populates="icms_c190")

    __table_args__ = (
        UniqueConstraint("tenant_id", "chv_nfe", "cst_icms", "cfop", "aliq_icms", name="uq_icms_c190"),
    )
