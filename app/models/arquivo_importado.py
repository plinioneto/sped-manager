from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from app.models.base import Base


class ArquivoImportado(Base):
    __tablename__ = "arquivos_importados"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    nome_original = Column(String, nullable=False)
    nome_padronizado = Column(String, nullable=False)
    cnpj = Column(String(14), nullable=False)
    periodo_ini = Column(String(8), nullable=False)
    periodo_fin = Column(String(8), nullable=False)
    status = Column(String, default="pendente")
    erro_msg = Column(String)
    criado_em = Column(DateTime, default=datetime.utcnow)
    processado_em = Column(DateTime)