from sqlalchemy.orm import Session
from app.models.produto import Produto
from app.repositories.base_repo import BaseRepository

class ProdutoRepository(BaseRepository):
    def listar(self):
        return (
            self.session.query(Produto)
            .filter(Produto.tenant_id == self.tenant_id)
            .all()
        )

    def buscar_por_codigo(self, codigo: str):
        return (
            self.session.query(Produto)
            .filter(
                Produto.tenant_id == self.tenant_id,
                Produto.codigo == codigo
            )
            .first()
        )

    def salvar(self, produto: Produto):
        produto.tenant_id = self.tenant_id
        self.session.add(produto)
        self.session.commit()
        self.session.refresh(produto)
        return produto

    def deletar(self, produto_id: int):
        produto = (
            self.session.query(Produto)
            .filter(
                Produto.tenant_id == self.tenant_id,
                Produto.id == produto_id
            )
            .first()
        )
        if produto:
            self.session.delete(produto)
            self.session.commit()