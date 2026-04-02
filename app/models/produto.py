from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, UniqueConstraint, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    cod_item = Column(String, nullable=False)
    descr_item = Column(String, nullable=False)
    cod_barra = Column(String)
    unid_inv = Column(String(6))
    tipo_item = Column(String)
    cod_ncm = Column(String(8))
    cest = Column(String)
    aliq_icms = Column(Float, default=0.0)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Padronização de descrição
    descricao_padrao     = Column(String(200))
    tipo_produto         = Column(String(60))    # REFRIGERANTE, BISCOITO, LEITE...
    tipo_embalagem       = Column(String(30))    # PET, LATA, VIDRO, SACO...
    peso_volume_valor    = Column(Numeric(12, 3))
    peso_volume_unidade  = Column(String(10))    # ML, L, G, KG, UN...
    score_padronizacao   = Column(Numeric(5, 4)) # 0.0000 a 1.0000
    origem_padronizacao  = Column(String(20))    # regra|fuzzy|embedding|llm|manual
    revisao_necessaria   = Column(Boolean, default=False)

    # Marca (FK global — sem tenant)
    marca_id = Column(Integer, ForeignKey("marcas.id"), nullable=True)

    # Classificação (FK global — sem tenant)
    categoria_id    = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    grupo_id        = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    departamento_id = Column(Integer, ForeignKey("departamentos.id"), nullable=True)
    score_categoria = Column(Numeric(5, 4))  # confiança da classificação automática

    __table_args__ = (
        UniqueConstraint('tenant_id', 'cod_item', name='uq_tenant_produto'),
    )

    tenant       = relationship("Tenant", back_populates="produtos")
    marca        = relationship("Marca", back_populates="produtos")
    categoria    = relationship("Categoria", back_populates="produtos")
    grupo        = relationship("Grupo")
    departamento = relationship("Departamento")