"""
Importação em lote de NFC-e / NF-e XML para o banco de produção (Supabase).

Funciona com SQLite (dev) e PostgreSQL (prod) — usa o DATABASE_URL do .env.

Estrutura de pastas esperada (qualquer nível de profundidade):
    PASTA_BASE/
        CAIXA01/2025/01/*.xml
        CAIXA01/2025/01/Transmitidos/*.xml
        ...

Pastas ignoradas automaticamente: Contingencia, ErroTransmissao

Uso:
    python scripts/importar_xmls_bulk.py --pasta "D:/data/Franmak/XML DE NFCE" --cnpj 12345678000190
    python scripts/importar_xmls_bulk.py --pasta "..." --cnpj ... --ano 2025
    python scripts/importar_xmls_bulk.py --pasta "..." --cnpj ... --ano 2025 --mes 01
    python scripts/importar_xmls_bulk.py --pasta "..." --cnpj ... --dry-run

Flags:
    --ano                filtra arquivos cujo caminho contenha o ano (ex: .../2025/...)
    --mes                filtra arquivos cujo caminho contenha o mês (ex: .../01/...)
    --batch              tamanho do lote para commit (default: 200)
    --skip-padronizacao  não roda pipeline de categorização (mais rápido; rode backfill depois)
    --dry-run            lista arquivos encontrados sem importar
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from app.utils.db import get_db
from app.models.tenant import Tenant
from app.parser.xml_parser import XmlParser


# ---------------------------------------------------------------------------
# Coleta de arquivos
# ---------------------------------------------------------------------------

PASTAS_IGNORADAS = {"contingencia", "errotransmissao"}


def coletar_xmls(pasta: Path, ano: str | None, mes: str | None) -> list[Path]:
    """Retorna lista de .xml sob `pasta`, ignorando Contingencia/ErroTransmissao."""
    arquivos = []
    for arq in sorted(pasta.rglob("*.xml")):
        partes = arq.parts
        # ignora pastas de contingência e erros de transmissão
        if any(p.lower() in PASTAS_IGNORADAS for p in partes):
            continue
        if ano and ano not in partes:
            continue
        if mes and mes not in partes:
            continue
        arquivos.append(arq)
    return arquivos


# ---------------------------------------------------------------------------
# Importação em lote
# ---------------------------------------------------------------------------

def importar(pasta: Path, cnpj: str, ano: str | None, mes: str | None,
             batch_size: int, skip_padronizacao: bool, dry_run: bool):

    # Busca tenant
    with get_db() as db:
        tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj).first()
        if not tenant:
            print(f"ERRO: Tenant com CNPJ {cnpj} não encontrado no banco.")
            sys.exit(1)
        tenant_id   = tenant.id
        tenant_nome = tenant.nome
        tenant_cnpj = tenant.cnpj

    print(f"Tenant : {tenant_nome} ({tenant_cnpj})")

    # Coleta arquivos
    print(f"Pasta  : {pasta}")
    xmls = coletar_xmls(pasta, ano, mes)
    print(f"XMLs   : {len(xmls):,} arquivos encontrados")

    if dry_run:
        for x in xmls[:20]:
            print(f"  {x}")
        if len(xmls) > 20:
            print(f"  ... e mais {len(xmls) - 20} arquivos")
        return

    if not xmls:
        print("Nenhum arquivo encontrado.")
        return

    # Contadores
    total       = len(xmls)
    concluidos  = 0
    duplicatas  = 0
    invalidos   = 0
    erros       = 0
    t_inicio    = time.time()

    if skip_padronizacao:
        print("  (padronização desativada — rode backfill_padronizacao.py depois)")

    # Reconecta a cada RECONNECT_EVERY batches para evitar quedas do pooler/Supabase
    RECONNECT_EVERY = 5   # lotes de batch_size arquivos por sessão (reconecta a cada ~1000 arq)

    # Cache compartilhado entre sessões (evita recarregar do banco a cada reconexão)
    _cache_chaves: set = set()
    _cache_produtos: set = set()
    _cache_participantes: set = set()
    _cache_marcas: dict = {}
    _cache_aquecido = False

    lote_na_sessao = 0  # quantos commits já fizemos nesta sessão
    db_ctx = get_db()
    db = db_ctx.__enter__()

    try:
        parser = XmlParser(db, tenant_id, tenant_cnpj=tenant_cnpj, skip_padronizacao=skip_padronizacao)
        print("  Carregando cache em memória...", end="", flush=True)
        n_chaves, n_prod = parser.warmup()
        _cache_chaves        = parser._cache_chaves
        _cache_produtos      = parser._cache_produtos
        _cache_participantes = parser._cache_participantes
        _cache_marcas        = parser._cache_marcas
        _cache_aquecido = True
        print(f" {n_chaves:,} chaves, {n_prod:,} produtos")

        # Acumula arquivos em lote; processa com 1 flush por lote (não por documento)
        batch: list[tuple[bytes, str]] = []

        for i, caminho in enumerate(xmls, 1):
            try:
                batch.append((caminho.read_bytes(), caminho.name))
            except Exception as e:
                erros += 1
                print(f"\n  ERRO ao ler [{caminho.name}]: {e}")

            fim_lote = len(batch) >= batch_size or i == total
            if not fim_lote:
                continue

            # ── processa o lote acumulado ──────────────────────────────────
            if batch:
                try:
                    res = parser.processar_lote(batch)
                    concluidos += res["concluidos"]
                    duplicatas += res["duplicatas"]
                    invalidos  += res["invalidos"]
                except Exception as e:
                    erros += len(batch)
                    print(f"\n  ERRO no lote [{i}]: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                batch = []

            # ── commit + limpa identity map ────────────────────────────────
            try:
                db.commit()
                db.expunge_all()
            except Exception as e:
                print(f"\n  ERRO no commit do lote {i}: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass

            lote_na_sessao += 1

            # ── progresso ──────────────────────────────────────────────────
            elapsed    = time.time() - t_inicio
            velocidade = i / elapsed if elapsed else 0
            restante   = (total - i) / velocidade if velocidade else 0
            print(
                f"\r  {i:>7,}/{total:,}  "
                f"✓{concluidos:,}  dup:{duplicatas:,}  inv:{invalidos:,}  err:{erros}  "
                f"{velocidade:.0f} arq/s  "
                f"~{int(restante//60)}min restantes",
                end="", flush=True
            )

            # ── reconexão periódica ────────────────────────────────────────
            if lote_na_sessao >= RECONNECT_EVERY:
                db_ctx.__exit__(None, None, None)
                lote_na_sessao = 0
                db_ctx = get_db()
                db = db_ctx.__enter__()
                parser = XmlParser(db, tenant_id, tenant_cnpj=tenant_cnpj,
                                   skip_padronizacao=skip_padronizacao)
                # Reutiliza todos os caches — não volta ao banco
                parser._cache_chaves        = _cache_chaves
                parser._cache_produtos      = _cache_produtos
                parser._cache_participantes = _cache_participantes
                parser._cache_marcas        = _cache_marcas

    finally:
        db_ctx.__exit__(None, None, None)

    elapsed = time.time() - t_inicio
    print(f"\n\n{'='*60}")
    print(f"Concluído em {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Importados : {concluidos:,}")
    print(f"  Duplicatas : {duplicatas:,}")
    print(f"  Inválidos  : {invalidos:,}")
    print(f"  Erros      : {erros}")
    print(f"  Velocidade : {total/elapsed:.0f} arq/s (média)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importação em lote de XMLs NFC-e/NF-e")
    parser.add_argument("--pasta",   required=True, help="Pasta raiz com os XMLs")
    parser.add_argument("--cnpj",    required=True, help="CNPJ do tenant (só dígitos)")
    parser.add_argument("--ano",     default=None,  help="Filtro de ano (ex: 2025)")
    parser.add_argument("--mes",     default=None,  help="Filtro de mês (ex: 01)")
    parser.add_argument("--batch",              type=int, default=200, help="Tamanho do lote (default: 200)")
    parser.add_argument("--skip-padronizacao", action="store_true", help="Pula categorização (rode backfill depois)")
    parser.add_argument("--dry-run",           action="store_true", help="Apenas lista arquivos, não importa")
    args = parser.parse_args()

    pasta = Path(args.pasta)
    if not pasta.exists():
        print(f"ERRO: pasta não encontrada: {pasta}")
        sys.exit(1)

    importar(
        pasta              = pasta,
        cnpj               = re.sub(r"\D", "", args.cnpj),
        ano                = args.ano,
        mes                = args.mes,
        batch_size         = args.batch,
        skip_padronizacao  = args.skip_padronizacao,
        dry_run            = args.dry_run,
    )
