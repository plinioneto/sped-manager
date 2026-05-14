"""
Popula as tabelas fabricantes e marcas a partir da tabela do arquivo .md.

Uso:
    cd D:\Data Science\Projeto SPED\Dashboard\sped-manager
    python scripts/seed_fabricantes_marcas.py

Normalização aplicada: maiúsculas + remoção de acentos (padrão do pipeline).
Registros já existentes são ignorados (sem sobrescrever).
"""

import sys
import unicodedata
from pathlib import Path

# Adiciona a raiz do projeto ao path para importar app.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.utils.db import get_db
from app.models.fabricante import Fabricante
from app.models.marca import Marca


# ── Dados da tabela (fabricante → [marcas]) ───────────────────────────────────
# Extraído de tabela_fabricantes_marcas_supermercados_brasil_2026.md

DADOS: list[tuple[str, list[str]]] = [
    ("Nestlé",               ["Nescafé", "Nescau", "Leite Moça", "KitKat", "Passatempo", "Bono", "Negresco", "Galak", "Charge", "Prestígio", "Maggi", "Purina"]),
    ("Unilever",             ["Hellmann's", "Knorr", "Kibon", "Dove", "Rexona", "OMO", "Comfort", "Seda", "Tresemmé", "Lux"]),
    ("Ambev",                ["Brahma", "Skol", "Antarctica", "Guaraná Antarctica", "Pepsi", "H2OH!", "Gatorade", "Budweiser", "Stella Artois", "Corona", "Beats",
                              # Cervejas adicionais Ambev
                              "Bohemia", "Patagonia", "Serramalte", "Polar", "Caracu",
                              "Colorado", "Wals", "Goose Island",
                              "Spaten", "Franziskaner", "Leffe", "Hoegaarden", "Becks", "Löwenbräu"]),
    ("Coca-Cola FEMSA",      ["Coca-Cola", "Fanta", "Sprite", "Schweppes", "Del Valle", "Crystal", "Powerade", "Monster", "Ades"]),
    ("PepsiCo",              ["Pepsi", "Elma Chips", "Ruffles", "Doritos", "Cheetos", "Toddynho", "Quaker", "Gatorade", "H2OH!"]),
    ("Mondelez",             ["Lacta", "Oreo", "Bis", "Trident", "Club Social", "Tang", "Halls", "Sonho de Valsa", "Bubbaloo"]),
    ("BRF",                  ["Sadia", "Perdigão", "Qualy", "Chester", "Confidence", "Claybom"]),
    ("JBS",                  ["Seara", "Friboi", "Doriana", "Massa Leve", "Swift"]),
    ("Aurora",               ["Aurora", "Nobre", "Peperi", "Gran Corte"]),
    ("Marfrig",              ["Bassi", "Montana", "Pampeano"]),
    ("Danone",               ["Danone", "Activia", "Danoninho", "YoPRO", "Bonafont", "Silk"]),
    ("Lactalis",             ["Parmalat", "Batavo", "Elegê", "Poços de Caldas", "Président"]),
    ("Piracanjuba",          ["Piracanjuba", "LeitBom", "Emana", "ChocoBom"]),
    ("Italac",               ["Italac", "Crioulo", "Sublime"]),
    ("Ypê",                  ["Ypê", "Assolan", "Atol", "Perfex", "Tixan"]),
    ("Bombril",              ["Bombril", "Mon Bijou", "Limpol", "Pinho Bril", "Sapólio Radium"]),
    ("Colgate-Palmolive",    ["Colgate", "Sorriso", "Palmolive", "Protex", "Ajax", "Pinho Sol"]),
    ("Procter & Gamble",     ["Gillette", "Pantene", "Pampers", "Ariel", "Downy", "Oral-B", "Head & Shoulders"]),
    ("Kimberly-Clark",       ["Neve", "Scott", "Intimus", "Huggies", "Kleenex"]),
    ("Hypera Pharma",        ["Benegrip", "Engov", "Epocler", "Estomazil", "Biotônico Fontoura"]),
    ("Reckitt",              ["Veja", "Vanish", "SBP", "Luftal", "Jontex", "Finish", "Harpic"]),
    ("Flora",                ["Minuano", "Francis", "Albany", "Assim", "Neutrox", "Kolene"]),
    ("Bunge",                ["Soya", "Primor", "Delícia", "Salada"]),
    ("Cargill",              ["Liza", "Elefante", "Pomarola", "Tarantella"]),
    ("M. Dias Branco",       ["Adria", "Vitarella", "Piraquê", "Richester", "Fortaleza", "Isabela"]),
    ("Bauducco",             ["Bauducco", "Visconti", "Pandurata", "Tommy"]),
    ("Marilan",              ["Marilan", "Teens", "Pit Stop"]),
    ("Santa Helena",         ["Paçoquita", "Crokíssimo", "Mendorato"]),
    ("Melitta",              ["Melitta", "Café Barão", "Café União"]),
    ("3 Corações",           ["3 Corações", "Santa Clara", "Kimimo", "Letícia"]),
    ("JDE Peet's",           ["Pilão", "L'OR", "Café do Ponto", "Caboclo"]),
    ("Heineken Brasil",      ["Heineken", "Amstel", "Eisenbahn", "Schin", "Devassa", "Baden Baden",
                              # Cervejas adicionais Heineken Brasil (via Femsa + Brasil Kirin)
                              "Kaiser", "Bavaria", "Tiger", "Lagunitas", "Kirin Ichiban",
                              "Birra Moretti", "Desperados", "Murphys", "Grimbergen", "Affligem",
                              "Glacial", "Blue Moon"]),
    ("Diageo",               ["Johnnie Walker", "Smirnoff", "Tanqueray", "Ypióca", "Guinness"]),
    ("Pernod Ricard",        ["Absolut", "Ballantine's", "Chivas Regal", "Beefeater"]),
    ("Kellogg's",            ["Kellogg's", "Sucrilhos", "Pringles"]),
    ("General Mills",        ["Yoki", "Kitano", "Häagen-Dazs"]),
    ("Ajinomoto",            ["Sazón", "Ajinomoto", "Mid", "Vono"]),
    ("Cepêra",               ["Cepêra", "Bonare"]),
    ("Josapar",              ["Tio João", "Meu Biju", "SupraSoy"]),
    ("Camil",                ["Camil", "União", "Coqueiro", "Santa Amália"]),
    ("J. Macêdo",            ["Dona Benta", "Sol", "Petybon", "Brandini"]),
    ("Hershey's",            ["Hershey's", "Reese's"]),
    ("Ferrero",              ["Ferrero Rocher", "Nutella", "Kinder", "Tic Tac"]),
    ("Mars",                 ["M&M's", "Snickers", "Twix", "Pedigree", "Whiskas"]),
    ("Garoto",               ["Serenata de Amor", "Talento", "Baton", "Garoto"]),

    # ── Cervejas — fabricantes nacionais ─────────────────────────────────────
    ("Grupo Petrópolis",     ["Itaipava", "Crystal", "Petra", "Black Princess", "Lokal", "Cabaré"]),
    ("Cerpa",                ["Cerpa", "Crolant"]),

    # ── Cervejas — importadas (Alemanha) ─────────────────────────────────────
    ("Erdinger Weissbrau",   ["Erdinger"]),
    ("Paulaner Brauerei",    ["Paulaner", "Hacker-Pschorr"]),
    ("Weihenstephaner",      ["Weihenstephaner"]),
    ("Warsteiner Brauerei",  ["Warsteiner"]),
    ("Bitburger Braugruppe", ["Bitburger", "König Pilsener"]),

    # ── Cervejas — importadas (Bélgica) ──────────────────────────────────────
    ("Duvel Moortgat",       ["Duvel", "Vedett", "La Chouffe", "Liefmans"]),
    ("Abbaye de Scourmont",  ["Chimay"]),

    # ── Confeitaria / balas ──────────────────────────────────────────────────
    ("Fini",                       ["Fini"]),

    # ── Cervejas — especiais / adicionais ────────────────────────────────────
    ("Coca-Cola FEMSA",            ["Kuat", "Therezópolis"]),
    ("Cervejaria Cidade Imperial", ["Império", "Puro Malte Pilsen"]),
    ("Cervejaria Brüder",          ["BG"]),
    ("Hijos de Rivera",            ["Estrella Galicia"]),

    # ── Cervejas — artesanais brasileiras ────────────────────────────────────
    ("Cervejaria Backer",    ["Backer", "Leopoldina"]),
    ("Cervejaria Krug Bier", ["Krug Bier"]),
    ("Cervejaria Dado Bier", ["Dado Bier"]),
    ("Cervejaria Saint Bier",["Saint Bier"]),
    ("Seasons Cervejaria",   ["Seasons"]),
    ("Cervejaria Coruja",    ["Coruja"]),
    ("Cervejaria 2 Cabeças", ["2 Cabeças"]),
    ("Dama Bier",            ["Dama Bier"]),
    ("Way Beer",             ["Way Beer"]),
]


# ── Normalização ──────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """Remove acentos e converte para maiúsculas."""
    nfkd = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return sem_acento.upper().strip()


# ── Seed ──────────────────────────────────────────────────────────────────────

def main():
    inseridos_fabs  = 0
    ignorados_fabs  = 0
    inseridas_marcas = 0
    ignoradas_marcas = 0

    with get_db() as db:
        try:
            for fab_original, marcas_lista in DADOS:
                fab_nome = normalizar(fab_original)

                # Fabricante — cria se não existir
                fab_obj = db.query(Fabricante).filter(Fabricante.nome == fab_nome).first()
                if not fab_obj:
                    fab_obj = Fabricante(nome=fab_nome, ativo=True)
                    db.add(fab_obj)
                    db.flush()
                    inseridos_fabs += 1
                    print(f"  [FAB +] {fab_nome}")
                else:
                    ignorados_fabs += 1
                    print(f"  [FAB =] {fab_nome} (já existe)")

                # Marcas
                for mrc_original in marcas_lista:
                    mrc_nome = normalizar(mrc_original)
                    if not mrc_nome:
                        continue
                    existing = db.query(Marca).filter(Marca.nome == mrc_nome).first()
                    if existing:
                        ignoradas_marcas += 1
                        continue
                    mrc_obj = Marca(
                        nome=mrc_nome,
                        fabricante_id=fab_obj.id,
                        ativo=True,
                    )
                    db.add(mrc_obj)
                    inseridas_marcas += 1
                    print(f"      [MRC +] {mrc_nome}")

            db.commit()

        except Exception as e:
            db.rollback()
            print(f"\n[ERRO] {e}")
            raise

    print("-" * 37)
    print("Concluido!")
    print(f"  Fabricantes inseridos : {inseridos_fabs}")
    print(f"  Fabricantes ignorados : {ignorados_fabs}")
    print(f"  Marcas inseridas      : {inseridas_marcas}")
    print(f"  Marcas ignoradas      : {ignoradas_marcas}")
    print("-" * 37)


if __name__ == "__main__":
    main()
