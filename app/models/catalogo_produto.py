from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class CatalogoProduto(Base):
    __tablename__ = "catalogo_produtos"

    id                  = Column(Integer, primary_key=True, index=True)
    cod_barra           = Column(String(14), unique=True, nullable=False, index=True)

    descricao_padrao    = Column(String(200))
    tipo_produto        = Column(String(60))
    tipo_embalagem      = Column(String(30))
    peso_volume_valor   = Column(Numeric(12, 3))
    peso_volume_unidade = Column(String(10))

    categoria_id        = Column(Integer, ForeignKey("categorias_produto.id"),    nullable=True)
    grupo_id            = Column(Integer, ForeignKey("grupos_produto.id"),         nullable=True)
    departamento_id     = Column(Integer, ForeignKey("departamentos_produto.id"), nullable=True)
    marca_id            = Column(Integer, ForeignKey("marcas.id"),         nullable=True)

    score_categoria     = Column(Numeric(5, 4))
    origem_padronizacao = Column(String(20))  # regra | manual | catalogo
    atualizado_em       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria    = relationship("Categoria")
    grupo        = relationship("Grupo")
    departamento = relationship("Departamento")
    marca        = relationship("Marca")
