from sqlalchemy.orm import Session
from app.models.documento_fiscal import DocumentoFiscal
from app.repositories.base_repo import BaseRepository

class DocumentoRepository(BaseRepository):
    def listar(self):
        return (
            self.session.query(DocumentoFiscal)
            .filter(DocumentoFiscal.tenant_id == self.tenant_id)
            .all()
        )

    def salvar(self, documento: DocumentoFiscal):
        documento.tenant_id = self.tenant_id
        self.session.add(documento)
        self.session.commit()
        self.session.refresh(documento)
        return documento