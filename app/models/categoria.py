from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class Departamento(Base):
    """
    Nível 1 da hierarquia de categorias — global, sem tenant_id.
    Ex: ACOUGUE, BEBIDAS, LIMPEZA, PERFUMARIA.
    """
    __tablename__ = "departamentos_produto"

    id          = Column(Integer, primary_key=True)
    descricao   = Column(String(100), nullable=False, unique=True)

    grupos      = relationship("Grupo", back_populates="departamento")


class Grupo(Base):
    """
    Nível 2 da hierarquia de categorias — global, sem tenant_id.
    Ex: CERVEJAS, REFRIGERANTE, BISCOITO DOCE, LATICINIOS.
    """
    __tablename__ = "grupos_produto"

    id              = Column(Integer, primary_key=True)
    departamento_id = Column(Integer, ForeignKey("departamentos_produto.id"), nullable=False)
    descricao       = Column(String(100), nullable=False)

    departamento    = relationship("Departamento", back_populates="grupos")
    categorias      = relationship("Categoria", back_populates="grupo")


class Categoria(Base):
    """
    Nível 3 da hierarquia de categorias — global, sem tenant_id.
    Ex: CERVEJA PURO MALTE, REFRIGERANTE COLA, PAO DE FORMA COMUM.
    """
    __tablename__ = "categorias_produto"

    id          = Column(Integer, primary_key=True)
    grupo_id    = Column(Integer, ForeignKey("grupos_produto.id"), nullable=False)
    descricao   = Column(String(150), nullable=False)

    grupo       = relationship("Grupo", back_populates="categorias")
    produtos    = relationship("Produto", back_populates="categoria")
