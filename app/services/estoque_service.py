from sqlalchemy.orm import Session
from app.repositories.produto_repo import ProdutoRepository

class EstoqueService:
    def __init__(self, session: Session, tenant_id: int):
        # cria o repository já com o tenant_id — todas as queries já ficam filtradas
        self.repo = ProdutoRepository(session, tenant_id)

    def listar_produtos(self):
        # retorna todos os produtos do tenant
        return self.repo.listar()

    def buscar_produto(self, codigo: str):
        # busca um produto pelo código — útil na leitura do SPED
        return self.repo.buscar_por_codigo(codigo)

    def atualizar_estoque(self, codigo: str, quantidade: float):
        # atualiza o saldo do estoque — chamado ao processar movimentações do SPED
        # quantidade pode ser positiva (entrada) ou negativa (saída)
        produto = self.repo.buscar_por_codigo(codigo)
        if produto:
            produto.estoque_atual += quantidade
            self.repo.salvar(produto)
        return produto