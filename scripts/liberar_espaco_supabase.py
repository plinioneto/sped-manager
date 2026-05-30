"""
Libera espaço no Supabase dropando a tabela efd_raw (bronze layer).

Os dados silver já estão processados em:
  - documentos_fiscais (C100)
  - itens_fiscais (C170)
  - icms_c190 (C190)
  - produtos (0200)
  - participantes (0150)
  - inventarios_h005/h010 (H005/H010)
  - estoques_k200 (K200)

A efd_raw só seria necessária para reprocessar o silver a partir do zero,
o que não é o caso. Pode ser recriada vazia para importações futuras.

Uso:
    python scripts/liberar_espaco_supabase.py --dry-run   # apenas mostra tamanhos
    python scripts/liberar_espaco_supabase.py             # executa o drop
"""

import argparse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL não configurada no .env")


def verificar_tamanhos(conn):
    rows = conn.execute(text("""
        SELECT
            relname AS tabela,
            pg_size_pretty(pg_total_relation_size(oid)) AS tamanho_total,
            pg_total_relation_size(oid) AS bytes
        FROM pg_class
        WHERE relkind = 'r'
          AND relname IN (
            'efd_raw', 'notas_fiscais', 'itens_nota_fiscal',
            'resumo_fiscal', 'produtos', 'fornecedores',
            'inventarios_h005', 'inventarios_h010', 'estoques_k200'
          )
        ORDER BY bytes DESC
    """)).fetchall()

    print("\nTamanho das tabelas:")
    print(f"{'Tabela':<25} {'Tamanho':>12}")
    print("-" * 38)
    for r in rows:
        print(f"{r.tabela:<25} {r.tamanho_total:>12}")

    total = conn.execute(text(
        "SELECT pg_size_pretty(pg_database_size(current_database()))"
    )).scalar()
    print(f"\nTotal do banco: {total}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas mostra tamanhos, não executa o drop")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        verificar_tamanhos(conn)

        if args.dry_run:
            print("\n[dry-run] Nenhuma alteração feita.")
            return

        contagem = conn.execute(text("SELECT COUNT(*) FROM efd_raw")).scalar()
        print(f"\nefd_raw tem {contagem:,} linhas.")
        print("Dropando tabela efd_raw...")

        conn.execute(text("DROP TABLE IF EXISTS efd_raw CASCADE"))
        conn.commit()
        print("efd_raw dropada com sucesso.")

        print("\nTamanhos após drop:")
        verificar_tamanhos(conn)

    print("\nAgora rode: .venv\\Scripts\\python.exe -m alembic upgrade head")


if __name__ == "__main__":
    main()
