from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy import Numeric
from sqlalchemy.orm import relationship
from app.models.base import Base

class ItemFiscal(Base):
    __tablename__ = "itens_nota_fiscal"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)
    chv_nfe = Column(String(44))
    documento_id = Column(Integer, ForeignKey("notas_fiscais.id"))
    num_item = Column(Integer)
    cod_item = Column(String)
    descr_compl = Column(String)
    qtd = Column(Numeric(15, 4), default=0.0)
    unid = Column(String(6))
    vl_item = Column(Numeric(15, 2), default=0.0)
    vl_desc = Column(Numeric(15, 2), default=0.0)
    cst_icms = Column(String)
    cfop = Column(String)
    vl_bc_icms = Column(Numeric(15, 2), default=0.0)
    aliq_icms = Column(Numeric(7, 4), default=0.0)
    vl_icms = Column(Numeric(15, 2), default=0.0)
    vl_pis = Column(Numeric(15, 2), default=0.0)
    vl_cofins = Column(Numeric(15, 2), default=0.0)
    cst_pis = Column(String(3))
    cst_cofins = Column(String(3))
    aliq_pis = Column(Numeric(7, 4), default=0.0)
    aliq_cofins = Column(Numeric(7, 4), default=0.0)

    documento = relationship("DocumentoFiscal", back_populates="itens")
    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'chv_nfe', 'num_item', name='uq_item_tenant_chave'),
    )
