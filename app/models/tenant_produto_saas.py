from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class TenantProdutoSaas(Base):
    """Entitlement: quais produtos SaaS estão ativos para cada tenant."""

    __tablename__ = "tenant_produtos_saas"

    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("lojas.id"), nullable=False, index=True)
    produto_saas_id = Column(Integer, ForeignKey("produtos_saas.id"), nullable=False)
    ativo           = Column(Boolean, default=False)
    ativado_em      = Column(DateTime, nullable=True)

    tenant       = relationship("Tenant")
    produto_saas = relationship("ProdutoSaas")

    __table_args__ = (
        UniqueConstraint("tenant_id", "produto_saas_id", name="uq_tenant_produto_saas"),
    )
