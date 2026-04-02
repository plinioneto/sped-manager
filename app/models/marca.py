from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class Marca(Base):
    """
    Marca comercial — entidade global, sem tenant_id.
    Ex: Dove (Fabricante: Unilever), Sadia (Fabricante: BRF).
    """
    __tablename__ = "marcas"

    id            = Column(Integer, primary_key=True, index=True)
    fabricante_id = Column(Integer, ForeignKey("fabricantes.id"), nullable=True)
    nome          = Column(String(100), nullable=False, unique=True)
    aliases       = Column(Text)        # JSON array: ["COCA","COCA-COLA","COCACOLA"]
    categoria     = Column(String(50))  # bebidas|limpeza|frios|higiene|alimentos...
    ativo         = Column(Boolean, default=True)

    fabricante = relationship("Fabricante", back_populates="marcas")
    produtos   = relationship("Produto", back_populates="marca")
