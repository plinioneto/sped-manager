from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Fabricante(Base):
    """
    Fabricante / grupo empresarial — entidade global, sem tenant_id.
    Ex: Unilever, BRF, Ambev, P&G.
    """
    __tablename__ = "fabricantes"

    id      = Column(Integer, primary_key=True, index=True)
    nome    = Column(String(100), nullable=False, unique=True)
    cnpj    = Column(String(14))   # nullable — nem todos têm CNPJ BR
    aliases = Column(Text)         # JSON array: ["UNILEVER BR", "UNILEVER BRASIL"]
    ativo   = Column(Boolean, default=True)

    marcas  = relationship("Marca", back_populates="fabricante")
