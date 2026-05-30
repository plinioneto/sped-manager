from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from app.models.base import Base


class EfdRaw(Base):
    __tablename__ = "efd_raw"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("lojas.id"), nullable=False)
    file_path = Column(String, nullable=False)
    num_linha = Column(Integer, nullable=False)
    tipo_registro = Column(String(10), nullable=False)
    conteudo_linha = Column(Text, nullable=False)
    ingest_timestamp = Column(DateTime, nullable=False)