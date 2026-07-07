"""
Roda o pipeline de padronização em todos os produtos que ainda não foram
processados (descricao_padrao IS NULL) ou que precisam de revisão.

Uso:
    cd D:\Data Science\Projeto SPED\Dashboard\sped-manager
    python scripts/backfill_padronizacao.py

Flags opcionais:
    --todos      Reprocessa TODOS os produtos (inclusive os já classificados)
    --tenant 3   Limita a um tenant específico (pelo ID)
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import or_

from app.utils.db import get_db
from app.models.produto import Produto
from app.models.marca import Marca
from app.services.produto_padronizacao import processar_descricao
from app.services.produto_padronizacao.identificador import carregar_marcas_do_banco


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--todos",  action="store_true", help="Reprocessa todos, inclusive classificados (preserva manuais)")
    parser.add_argument("--force",  action="store_true", help="Sobrescreve inclusive classificacoes manuais (cuidado!)")
    parser.add_argument("--tenant", type=int, default=None, help="Limita ao tenant ID informado")
    args = parser.parse_args()

    with get_db() as db:
        # Carrega marcas do banco no índice antes de processar
        carregar_marcas_do_banco(db)

        q = db.query(Produto)

        if args.tenant:
            q = q.filter(Produto.tenant_id == args.tenant)

        if not args.todos:
            q = q.filter(Produto.descricao_padrao.is_(None))

        # Sempre protege classificações manuais, exceto com --force
        if not args.force:
            q = q.filter(
                or_(
                    Produto.origem_padronizacao.is_(None),
                    ~Produto.origem_padronizacao.in_(["manual", "manual_sem_cat"]),
                )
            )

        produtos = q.order_by(Produto.tenant_id, Produto.descr_item).all()

        total = len(produtos)
        print(f"Produtos a processar: {total}")
        if total == 0:
            print("Nada a fazer.")
            return

        processados  = 0
        com_marca    = 0
        com_cat      = 0
        revisao      = 0
        erros        = 0

        for i, produto in enumerate(produtos, 1):
            try:
                resultado = processar_descricao(produto.descr_item, session=db)

                produto.descricao_padrao     = resultado.descricao_padrao
                produto.tipo_produto         = resultado.tipo_produto
                produto.tipo_embalagem       = resultado.tipo_embalagem
                produto.peso_volume_valor    = resultado.peso_volume_valor
                produto.peso_volume_unidade  = resultado.peso_volume_unidade
                produto.score_padronizacao   = resultado.score_confianca
                produto.origem_padronizacao  = resultado.origem
                produto.revisao_necessaria   = resultado.revisao_necessaria
                produto.categoria_id         = resultado.categoria_id
                produto.grupo_id             = resultado.grupo_id
                produto.departamento_id      = resultado.departamento_id
                produto.score_categoria      = resultado.score_categoria

                # Resolve marca_id
                if resultado.marca:
                    marca_obj = db.query(Marca).filter(Marca.nome == resultado.marca).first()
                    if marca_obj:
                        produto.marca_id = marca_obj.id
                        com_marca += 1

                if resultado.categoria_id or resultado.grupo_id:
                    com_cat += 1
                if resultado.revisao_necessaria:
                    revisao += 1

                processados += 1

                # Commit em lotes de 500
                if i % 500 == 0:
                    db.commit()
                    print(f"  {i}/{total} processados...")

            except Exception as e:
                erros += 1
                print(f"  [ERRO] {produto.cod_item} — {e}")

        db.commit()

    print()
    print("-" * 40)
    print(f"Concluido!")
    print(f"  Processados      : {processados}")
    print(f"  Com marca        : {com_marca}")
    print(f"  Com categoria    : {com_cat}")
    print(f"  Revisao manual   : {revisao}")
    print(f"  Erros            : {erros}")
    print(f"  Taxa classificac.: {com_cat/processados:.0%}" if processados else "")
    print("-" * 40)


if __name__ == "__main__":
    main()
