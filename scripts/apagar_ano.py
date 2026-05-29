"""
Remove documentos fiscais de um ano específico em lotes pequenos.
Projetado para funcionar mesmo com disco quase cheio no servidor.

Uso:
    python scripts/apagar_ano.py --cnpj 68514439000176 --ano 2023
    python scripts/apagar_ano.py --cnpj 68514439000176 --ano 2023 --confirmar
"""

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.utils.db import get_db
from app.models.tenant import Tenant

LOTE = 500  # documentos por vez — pequeno o suficiente para não criar temp files


def apagar(cnpj: str, ano: int, confirmar: bool):
    with get_db() as db:
        tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj).first()
        if not tenant:
            print(f"ERRO: Tenant com CNPJ {cnpj} não encontrado.")
            sys.exit(1)

        tid  = tenant.id
        nome = tenant.nome
        print(f"Tenant : {nome} ({cnpj})")
        print(f"Ano    : {ano}")

        # Conta só documentos (query simples, sem JOIN — não cria temp file)
        n_docs = db.execute(text(
            "SELECT COUNT(*) FROM documentos_fiscais "
            "WHERE tenant_id = :tid AND EXTRACT(YEAR FROM dt_doc) = :ano"
        ), {"tid": tid, "ano": ano}).scalar()

        print(f"\nDocumentos encontrados: {n_docs:,}")
        print(f"(itens e C190 serão apagados junto, em lotes de {LOTE})")

        if n_docs == 0:
            print("Nada a apagar.")
            return

        if not confirmar:
            print("\nUse --confirmar para executar a exclusão.")
            return

        # ── Apaga em lotes pequenos ────────────────────────────────────────
        total_docs = total_itens = total_c190 = 0
        t0 = time.time()

        while True:
            # Busca próximo lote de chaves
            rows = db.execute(text(
                "SELECT chv_nfe FROM documentos_fiscais "
                "WHERE tenant_id = :tid AND EXTRACT(YEAR FROM dt_doc) = :ano "
                "LIMIT :lote"
            ), {"tid": tid, "ano": ano, "lote": LOTE}).fetchall()

            if not rows:
                break

            chaves = [r[0] for r in rows]

            # Apaga filhos antes do pai
            r_c190 = db.execute(text(
                "DELETE FROM icms_c190 WHERE chv_doc = ANY(:chaves)"
            ), {"chaves": chaves})

            r_itens = db.execute(text(
                "DELETE FROM itens_fiscais WHERE chv_doc = ANY(:chaves)"
            ), {"chaves": chaves})

            r_docs = db.execute(text(
                "DELETE FROM documentos_fiscais WHERE chv_nfe = ANY(:chaves)"
            ), {"chaves": chaves})

            db.commit()

            total_docs  += r_docs.rowcount
            total_itens += r_itens.rowcount
            total_c190  += r_c190.rowcount

            elapsed = time.time() - t0
            print(
                f"\r  {total_docs:>7,}/{n_docs:,} docs apagados  "
                f"({total_itens:,} itens, {total_c190:,} C190)  "
                f"{total_docs/elapsed:.0f} docs/s",
                end="", flush=True
            )

        print(f"\n\nConcluído em {time.time()-t0:.0f}s")
        print(f"  Documentos : {total_docs:,}")
        print(f"  Itens      : {total_itens:,}")
        print(f"  C190       : {total_c190:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnpj",      required=True)
    parser.add_argument("--ano",       required=True, type=int)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    apagar(
        cnpj      = re.sub(r"\D", "", args.cnpj),
        ano       = args.ano,
        confirmar = args.confirmar,
    )
