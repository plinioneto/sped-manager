from sqlalchemy.orm import Session
from app.repositories.documento_repo import DocumentoRepository
from app.repositories.produto_repo import ProdutoRepository

class SpedService:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id
        # instancia os dois repositories que vai precisar
        self.doc_repo = DocumentoRepository(session, tenant_id)
        self.prod_repo = ProdutoRepository(session, tenant_id)

    def processar_arquivo(self, conteudo: str):
        # ponto de entrada para o parser
        # futuramente vai:
        # 1. chamar seu parser (local ou Databricks)
        # 2. salvar documentos fiscais via doc_repo
        # 3. atualizar estoque via prod_repo
        return {
            "documentos": [],
            "produtos": [],
            "status": "aguardando parser"
        }