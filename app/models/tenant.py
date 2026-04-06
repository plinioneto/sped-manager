from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id             = Column(Integer, primary_key=True, index=True)
    nome           = Column(String, nullable=False)
    cnpj           = Column(String(14), unique=True, nullable=False)
    ativo          = Column(Boolean, default=True)
    criado_em      = Column(DateTime, default=datetime.utcnow)
    grupo_id       = Column(Integer, ForeignKey("grupos_empresariais.id"), nullable=True)
    senha_hash     = Column(String, nullable=True)
    codigo_acesso  = Column(String, unique=True, nullable=True)

    grupo = relationship("GrupoEmpresarial", back_populates="tenants")

    produtos = relationship("Produto", back_populates="tenant")
    documentos_fiscais = relationship("DocumentoFiscal", back_populates="tenant")
    arquivos_importados = relationship("ArquivoImportado")
    efd_raw = relationship("EfdRaw")
    participantes = relationship("Participante", back_populates="tenant")