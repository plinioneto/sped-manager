import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.catalogo_produto import CatalogoProduto

_EAN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')


def ean_valido(cod_barra: str) -> bool:
    if not cod_barra:
        return False
    return bool(_EAN_RE.match(cod_barra.strip()))


class CatalogoProdutoRepository:
    def __init__(self, session: Session):
        self.session = session

    def buscar_por_ean(self, cod_barra: str) -> CatalogoProduto | None:
        return (
            self.session.query(CatalogoProduto)
            .filter(CatalogoProduto.cod_barra == cod_barra.strip())
            .first()
        )

    def upsert_from_produto(self, produto, cod_barra: str) -> CatalogoProduto:
        """Cria ou atualiza entrada no catálogo global com base em um Produto já classificado.
        Nunca sobrescreve entradas com origem='manual'.
        """
        entrada = self.buscar_por_ean(cod_barra)

        if entrada:
            if entrada.origem_padronizacao == 'manual':
                return entrada
            entrada.descricao_padrao    = produto.descricao_padrao
            entrada.tipo_produto        = produto.tipo_produto
            entrada.tipo_embalagem      = produto.tipo_embalagem
            entrada.peso_volume_valor   = produto.peso_volume_valor
            entrada.peso_volume_unidade = produto.peso_volume_unidade
            entrada.categoria_id        = produto.categoria_id
            entrada.grupo_id            = produto.grupo_id
            entrada.departamento_id     = produto.departamento_id
            entrada.marca_id            = produto.marca_id
            entrada.score_categoria     = produto.score_categoria
            entrada.origem_padronizacao = produto.origem_padronizacao or 'regra'
            entrada.atualizado_em       = datetime.utcnow()
        else:
            entrada = CatalogoProduto(
                cod_barra           = cod_barra.strip(),
                descricao_padrao    = produto.descricao_padrao,
                tipo_produto        = produto.tipo_produto,
                tipo_embalagem      = produto.tipo_embalagem,
                peso_volume_valor   = produto.peso_volume_valor,
                peso_volume_unidade = produto.peso_volume_unidade,
                categoria_id        = produto.categoria_id,
                grupo_id            = produto.grupo_id,
                departamento_id     = produto.departamento_id,
                marca_id            = produto.marca_id,
                score_categoria     = produto.score_categoria,
                origem_padronizacao = produto.origem_padronizacao or 'regra',
            )
            self.session.add(entrada)

        self.session.flush()
        return entrada
