from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base

class ItemFiscal(Base):
    __tablename__ = "itens_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    chv_doc = Column(String(44))
    documento_id = Column(Integer, ForeignKey("documentos_fiscais.id"))
    num_item = Column(Integer)
    cod_item = Column(String)
    descr_compl = Column(String)
    qtd = Column(Float, default=0.0)
    unid = Column(String(6))
    vl_item = Column(Float, default=0.0)
    vl_desc = Column(Float, default=0.0)
    cst_icms = Column(String)
    cfop = Column(String)
    vl_bc_icms = Column(Float, default=0.0)
    aliq_icms = Column(Float, default=0.0)
    vl_icms = Column(Float, default=0.0)
    vl_pis = Column(Float, default=0.0)
    vl_cofins = Column(Float, default=0.0)

    documento = relationship("DocumentoFiscal", back_populates="itens")
    tenant = relationship("Tenant")