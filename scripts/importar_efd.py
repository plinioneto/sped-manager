"""
Importação de arquivos EFD (.txt) para o banco de produção.

Fluxo:
    1. Arquivo bruto salvo no Cloudflare R2 (bronze)
    2. Parser processa diretamente em memória → silver no Supabase
    3. gold_kpis_mensais calculado e gravado no Supabase

Uso:
    python scripts/importar_efd.py --pasta "D:/data/cliente/EFDs"
    python scripts/importar_efd.py --arquivo "D:/data/cliente/jan2025.txt"
    python scripts/importar_efd.py --pasta "..." --dry-run
    python scripts/importar_efd.py --pasta "..." --skip-padronizacao

Flags:
    --pasta               pasta com arquivos EFD .txt (recursivo)
    --arquivo             importa um único arquivo EFD
    --cnpj                valida que os arquivos pertencem a este CNPJ (opcional)
    --skip-padronizacao   não roda pipeline de categorização (rode backfill depois)
    --dry-run             lista arquivos encontrados sem importar
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from app.utils.db import get_db
from app.utils.r2 import upload_bytes, r2_key_efd
from app.models.tenant import Tenant
from app.models.arquivo_importado import ArquivoImportado
from app.parser.renomeador import processar_renomeacao
from app.parser.silver import SilverProcessor
from app.services.gold_kpis_service import calcular_kpis_arquivo


def coletar_efds(pasta: Path) -> list[Path]:
    return sorted(pasta.rglob("*.txt"))


def arquivo_ja_importado(db, tenant_id: int, nome_padronizado: str) -> bool:
    return db.query(ArquivoImportado).filter(
        ArquivoImportado.tenant_id       == tenant_id,
        ArquivoImportado.nome_padronizado == nome_padronizado,
        ArquivoImportado.status          == "concluido",
    ).first() is not None


def importar(
    arquivos: list[Path],
    cnpj_filtro: str | None,
    skip_padronizacao: bool,
    dry_run: bool,
):
    print(f"Arquivos : {len(arquivos):,} encontrados")

    if dry_run:
        for a in arquivos[:20]:
            print(f"  {a}")
        if len(arquivos) > 20:
            print(f"  ... e mais {len(arquivos) - 20} arquivos")
        return

    if not arquivos:
        print("Nenhum arquivo encontrado.")
        return

    total      = len(arquivos)
    importados = 0
    ignorados  = 0
    erros      = 0
    t_inicio   = time.time()

    if skip_padronizacao:
        print("  (padronização desativada — rode backfill_padronizacao.py depois)\n")

    for i, caminho in enumerate(arquivos, 1):
        print(f"[{i}/{total}] {caminho.name}", end=" ... ", flush=True)

        # Lê o arquivo
        try:
            conteudo = caminho.read_text(encoding="latin-1")
        except Exception as e:
            print(f"ERRO ao ler: {e}")
            erros += 1
            continue

        # Extrai metadados do EFD
        try:
            metadados = processar_renomeacao(conteudo, caminho.name)
        except ValueError as e:
            print(f"ERRO no EFD: {e}")
            erros += 1
            continue

        cnpj_arquivo     = metadados["cnpj"]
        nome_padronizado = metadados["novo_nome"]

        if cnpj_filtro and cnpj_arquivo != cnpj_filtro:
            print(f"ignorado (CNPJ {cnpj_arquivo} ≠ {cnpj_filtro})")
            ignorados += 1
            continue

        with get_db() as db:
            tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj_arquivo).first()
            if not tenant:
                print(f"ignorado (tenant CNPJ {cnpj_arquivo} não cadastrado)")
                ignorados += 1
                continue

            tenant_id = tenant.id

            if arquivo_ja_importado(db, tenant_id, nome_padronizado):
                print("ignorado (já importado)")
                ignorados += 1
                continue

            # Registra com status pendente
            arquivo_reg = ArquivoImportado(
                tenant_id        =tenant_id,
                nome_original    =metadados["nome_original"],
                nome_padronizado =nome_padronizado,
                cnpj             =cnpj_arquivo,
                periodo_ini      =metadados["periodo_ini"],
                periodo_fin      =metadados["periodo_fin"],
                status           ="pendente",
            )
            db.add(arquivo_reg)
            db.commit()

            # 1. Salva no R2 (bronze)
            try:
                r2_key = r2_key_efd(cnpj_arquivo, nome_padronizado)
                upload_bytes(r2_key, conteudo.encode("latin-1"))
            except Exception as e:
                print(f"AVISO R2: {e} (continuando)")

            # 2. Processa silver diretamente do conteúdo
            try:
                if skip_padronizacao:
                    import app.parser.silver as _silver_mod
                    _orig = _silver_mod._PADRONIZACAO_DISPONIVEL
                    _silver_mod._PADRONIZACAO_DISPONIVEL = False

                silver    = SilverProcessor(db, tenant_id)
                resultado = silver.processar_conteudo(conteudo)

                if skip_padronizacao:
                    _silver_mod._PADRONIZACAO_DISPONIVEL = _orig

            except Exception as e:
                arquivo_reg.status   = "erro"
                arquivo_reg.erro_msg = f"Silver: {e}"
                db.commit()
                print(f"ERRO silver: {e}")
                erros += 1
                continue

            # 3. Calcula gold_kpis_mensais
            try:
                calcular_kpis_arquivo(db, tenant_id, metadados["periodo_ini"], metadados["periodo_fin"])
            except Exception as e:
                print(f"AVISO gold: {e} (continuando)")

            arquivo_reg.status       = "concluido"
            arquivo_reg.processado_em = datetime.utcnow()
            db.commit()

        importados += 1
        r = resultado
        print(
            f"OK  docs:{r.get('documentos', 0)}  "
            f"itens:{r.get('itens', 0)}  "
            f"produtos:{r.get('produtos_criados', 0)}  "
            f"participantes:{r.get('participantes', 0)}"
        )

    elapsed = time.time() - t_inicio
    print(f"\n{'='*60}")
    print(f"Concluído em {elapsed:.0f}s")
    print(f"  Importados : {importados}")
    print(f"  Ignorados  : {ignorados}")
    print(f"  Erros      : {erros}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importação de arquivos EFD .txt")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pasta",   help="Pasta com arquivos EFD .txt")
    group.add_argument("--arquivo", help="Caminho de um único arquivo EFD")
    parser.add_argument("--cnpj",              default=None, help="Valida CNPJ dos arquivos")
    parser.add_argument("--skip-padronizacao", action="store_true")
    parser.add_argument("--dry-run",           action="store_true")
    args = parser.parse_args()

    if args.pasta:
        pasta = Path(args.pasta)
        if not pasta.exists():
            print(f"ERRO: pasta não encontrada: {pasta}")
            sys.exit(1)
        arquivos = coletar_efds(pasta)
    else:
        arq = Path(args.arquivo)
        if not arq.exists():
            print(f"ERRO: arquivo não encontrado: {arq}")
            sys.exit(1)
        arquivos = [arq]

    importar(
        arquivos          = arquivos,
        cnpj_filtro       = re.sub(r"\D", "", args.cnpj) if args.cnpj else None,
        skip_padronizacao = args.skip_padronizacao,
        dry_run           = args.dry_run,
    )
