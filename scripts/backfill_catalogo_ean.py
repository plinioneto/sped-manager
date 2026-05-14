"""
Popula a tabela catalogo_produtos com produtos já classificados no banco.

Para cada Produto com EAN válido e classificado (categoria_id ou grupo_id preenchidos),
cria ou atualiza a entrada correspondente no catálogo global.

Uso:
    cd D:\Data Science\Projeto SPED\Dashboard\sped-manager
    python scripts/backfill_catalogo_ean.py

Flags opcionais:
    --dry-run       Simula sem gravar nada no banco
    --tenant 3      Limita a um tenant específico (pelo ID)
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.models  # noqa: F401 — garante que todos os models estão registrados

from app.utils.db import get_db
from app.models.produto import Produto
from app.repositories.catalogo_repo import CatalogoProdutoRepository, ean_valido


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar")
    parser.add_argument("--tenant",  type=int,            help="Limita a um tenant pelo ID")
    args = parser.parse_args()

    with get_db() as db:
        repo = CatalogoProdutoRepository(db)

        q = db.query(Produto).filter(
            (Produto.categoria_id.isnot(None)) | (Produto.grupo_id.isnot(None))
        )
        if args.tenant:
            q = q.filter(Produto.tenant_id == args.tenant)

        produtos = q.all()

        total       = len(produtos)
        validos     = 0
        criados     = 0
        atualizados = 0
        ignorados   = 0
        lote        = 0

        print(f"Produtos classificados encontrados: {total}")
        if args.dry_run:
            print("[DRY-RUN] Nenhuma alteração será gravada.")

        for p in produtos:
            if not ean_valido(p.cod_barra or ''):
                ignorados += 1
                continue

            validos += 1

            if args.dry_run:
                existente = repo.buscar_por_ean(p.cod_barra)
                if existente:
                    atualizados += 1
                else:
                    criados += 1
                continue

            existente = repo.buscar_por_ean(p.cod_barra)
            repo.upsert_from_produto(p, p.cod_barra)
            if existente:
                atualizados += 1
            else:
                criados += 1

            lote += 1
            if lote >= 500:
                db.commit()
                lote = 0

        if not args.dry_run and lote > 0:
            db.commit()

        print(f"\nResultado:")
        print(f"  Produtos sem EAN válido (ignorados): {ignorados}")
        print(f"  Produtos com EAN válido:             {validos}")
        print(f"  Entradas criadas no catálogo:        {criados}")
        print(f"  Entradas atualizadas no catálogo:    {atualizados}")
        if args.dry_run:
            print("  [DRY-RUN] Nenhuma escrita realizada.")


if __name__ == "__main__":
    main()
