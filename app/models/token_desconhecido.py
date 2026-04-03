from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.models.base import Base


class TokenDesconhecido(Base):
    """
    Tokens encontrados nas descrições de produtos que não foram reconhecidos
    por nenhum dicionário do pipeline (abreviações, marcas, categorias,
    embalagens, atributos, unidades).

    Entidade global (sem tenant_id) — serve como insumo para alimentar
    novos dicionários e ampliar a cobertura do pipeline.
    """
    __tablename__ = "tokens_desconhecidos"

    id            = Column(Integer, primary_key=True, index=True)
    token         = Column(String(100), nullable=False, unique=True, index=True)
    contagem      = Column(Integer, default=1, nullable=False)
    primeiro_visto = Column(DateTime, default=datetime.utcnow)
    ultimo_visto  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    exemplo       = Column(Text)   # descrição original onde o token apareceu
