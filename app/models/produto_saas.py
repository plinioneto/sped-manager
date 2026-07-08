from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.models.base import Base


class ProdutoSaas(Base):
    """Catálogo de produtos/módulos SaaS contratáveis (não confundir com `Produto`/`produtos`, que é o catálogo de SKUs fiscais)."""

    __tablename__ = "produtos_saas"

    id         = Column(Integer, primary_key=True, index=True)
    slug       = Column(String(60), unique=True, nullable=False)
    nome       = Column(String, nullable=False)
    descricao  = Column(String, nullable=True)
    ativo      = Column(Boolean, default=True)
    criado_em  = Column(DateTime, default=datetime.utcnow)
