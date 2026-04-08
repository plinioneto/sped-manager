"""
Atualiza aliases e categoria='bebidas' para marcas de cerveja no banco.

Aliases garantem que formas abreviadas ou alternativas encontradas em descrições
EFD de supermercados sejam corretamente identificadas pelo pipeline.

Regra de mesclagem: nunca sobrescreve aliases já existentes — apenas ADICIONA
os que estiverem faltando.

Uso:
    .venv/Scripts/python.exe scripts/seed_aliases_cervejas.py
"""

import sys
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.utils.db import get_session
from app.models.marca import Marca


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return sem_acento.upper().strip()


# ---------------------------------------------------------------------------
# Mapa: nome_normalizado → aliases
#
# Inclui:
#   - Cópias dos aliases do dicionário fixo (identificador.py) para marcas que
#     já existiam — garante que o DB seja autoridade e o dict fixo possa ser
#     simplificado no futuro.
#   - Aliases CRÍTICOS para marcas novas (exclusivas do DB), sem os quais
#     formas abreviadas em EFD não seriam reconhecidas.
# ---------------------------------------------------------------------------

ALIASES_CERVEJAS: dict[str, list[str]] = {

    # ── AMBEV — copiados do dicionário fixo + variantes comuns ──────────────
    "BRAHMA":              ["BRAHMA"],
    "SKOL":                ["SKOL"],
    "ANTARCTICA":          ["ANTARCTICA", "ANTARCT", "ANTART"],
    "BOHEMIA":             ["BOHEMIA", "BOEMIA"],
    "STELLA ARTOIS":       ["STELLA", "STELLA ARTOIS"],
    "BUDWEISER":           ["BUDWEISER", "BUD"],
    "CORONA":              ["CORONA", "CORONA EXTRA"],
    "GUARANA ANTARCTICA":  ["GUARANA ANT", "GUARANA ANTARC"],
    "BEATS":               ["BEATS"],
    # Marcas adicionadas recentemente (só DB, sem aliases):
    "PATAGONIA":           ["PATAGONIA"],
    "SERRAMALTE":          ["SERRAMALTE", "SERRAM"],
    "POLAR":               ["POLAR"],
    "CARACU":              ["CARACU"],
    "COLORADO":            ["COLORADO"],
    "WALS":                ["WALS", "WAELS"],
    "GOOSE ISLAND":        ["GOOSE", "GOOSE ISLAND"],   # ← CRÍTICO: bigrama nem sempre aparece
    "SPATEN":              ["SPATEN"],
    "FRANZISKANER":        ["FRANZISKANER", "FRANZ"],
    "LEFFE":               ["LEFFE"],
    "HOEGAARDEN":          ["HOEGAARDEN", "HOEG"],
    "BECKS":               ["BECKS", "BECK S"],
    "LOWENBRAU":           ["LOWENBRAU", "LOWEN"],

    # ── HEINEKEN BRASIL — copiados do dicionário fixo + novos ───────────────
    "HEINEKEN":            ["HEINEKEN", "HEINEK"],
    "AMSTEL":              ["AMSTEL"],
    "EISENBAHN":           ["EISENBAHN", "EISENB"],
    "SCHIN":               ["SCHIN", "SCHINCARIOL"],
    "DEVASSA":             ["DEVASSA"],
    "BADEN BADEN":         ["BADEN BADEN", "BADEN"],
    # Marcas adicionadas recentemente:
    "KAISER":              ["KAISER"],
    "BAVARIA":             ["BAVARIA"],
    "TIGER":               ["TIGER"],
    "LAGUNITAS":           ["LAGUNITAS"],
    "KIRIN ICHIBAN":       ["KIRIN", "KIRIN ICHIBAN"],  # ← CRÍTICO: frequentemente só "KIRIN"
    "BIRRA MORETTI":       ["MORETTI", "BIRRA MORETTI"], # ← CRÍTICO: frequentemente só "MORETTI"
    "DESPERADOS":          ["DESPERADOS"],
    "MURPHYS":             ["MURPHYS", "MURPHY S", "MURPHY"],
    "GRIMBERGEN":          ["GRIMBERGEN"],
    "AFFLIGEM":            ["AFFLIGEM"],
    "GLACIAL":             ["GLACIAL"],
    "BLUE MOON":           ["BLUE MOON"],

    # ── DIAGEO ──────────────────────────────────────────────────────────────
    "GUINNESS":            ["GUINNESS"],

    # ── GRUPO PETROPOLIS ────────────────────────────────────────────────────
    "ITAIPAVA":            ["ITAIPAVA", "ITAIP"],
    "PETRA":               ["PETRA"],
    "BLACK PRINCESS":      ["BLACK PRINCESS"],
    "LOKAL":               ["LOKAL"],
    "CABARE":              ["CABARE"],

    # ── CERPA ───────────────────────────────────────────────────────────────
    "CERPA":               ["CERPA"],
    "CROLANT":             ["CROLANT"],

    # ── ALEMÃS ──────────────────────────────────────────────────────────────
    "ERDINGER":            ["ERDINGER"],
    "PAULANER":            ["PAULANER"],
    "HACKER-PSCHORR":      ["HACKER PSCHORR", "HACKER-PSCHORR", "HACKER"],  # ← CRÍTICO: hífen removido
    "WEIHENSTEPHANER":     ["WEIHENSTEPHANER", "WEIHEN"],
    "WARSTEINER":          ["WARSTEINER"],
    "BITBURGER":           ["BITBURGER"],
    "KONIG PILSENER":      ["KONIG PILSENER", "KONIG"],

    # ── BELGAS ──────────────────────────────────────────────────────────────
    "DUVEL":               ["DUVEL"],
    "VEDETT":              ["VEDETT"],
    "LA CHOUFFE":          ["CHOUFFE", "LA CHOUFFE"],  # ← CRÍTICO: "LA" frequentemente omitido
    "LIEFMANS":            ["LIEFMANS"],
    "CHIMAY":              ["CHIMAY"],

    # ── CRAFT BRASILEIRAS ───────────────────────────────────────────────────
    "BACKER":              ["BACKER"],
    "LEOPOLDINA":          ["LEOPOLDINA"],
    "KRUG BIER":           ["KRUG", "KRUG BIER"],      # ← CRÍTICO: "BIER" frequentemente omitido
    "DADO BIER":           ["DADO", "DADO BIER"],       # ← CRÍTICO: "BIER" frequentemente omitido
    "SAINT BIER":          ["SAINT BIER"],
    "SEASONS":             ["SEASONS"],
    "CORUJA":              ["CORUJA"],
    "2 CABECAS":           ["2 CABECAS", "DOIS CABECAS"],
    "DAMA BIER":           ["DAMA BIER", "DAMA"],
    "WAY BEER":            ["WAY BEER"],
}


def main():
    db = next(get_session())
    atualizadas = 0
    categoria_atualizadas = 0
    nao_encontradas: list[str] = []

    try:
        for marca_nome, novos_aliases in ALIASES_CERVEJAS.items():
            nome_norm = normalizar(marca_nome)
            marca_obj = db.query(Marca).filter(Marca.nome == nome_norm).first()

            if not marca_obj:
                nao_encontradas.append(nome_norm)
                continue

            changed = False

            # ── Atualiza categoria ──────────────────────────────────────────
            if marca_obj.categoria != "bebidas":
                marca_obj.categoria = "bebidas"
                changed = True
                categoria_atualizadas += 1

            # ── Mescla aliases ──────────────────────────────────────────────
            existentes: list[str] = []
            if marca_obj.aliases:
                try:
                    existentes = json.loads(marca_obj.aliases)
                except (ValueError, TypeError):
                    existentes = []

            existentes_upper = {a.upper() for a in existentes}
            adicionados = [a for a in novos_aliases if a.upper() not in existentes_upper]

            if adicionados:
                merged = existentes + adicionados
                marca_obj.aliases = json.dumps(merged, ensure_ascii=False)
                changed = True
                print(f"  [+] {nome_norm:<30} aliases: {adicionados}")
            else:
                print(f"  [=] {nome_norm:<30} aliases já ok")

            if changed:
                atualizadas += 1

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"\n[ERRO] {e}")
        raise
    finally:
        db.close()

    print("-" * 50)
    print(f"Concluído!")
    print(f"  Marcas atualizadas (aliases/cat): {atualizadas}")
    print(f"  Categoria 'bebidas' definida    : {categoria_atualizadas}")
    if nao_encontradas:
        print(f"  Não encontradas no banco        : {nao_encontradas}")
    print("-" * 50)


if __name__ == "__main__":
    main()
