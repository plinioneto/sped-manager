"""
Categorizador de produtos baseado em keyword matching.

Estratégia (Fase 1 — sem dependências externas):
  1. Carrega departamentos/grupos/categorias do banco (cache em memória).
  2. Para cada token da descrição expandida, verifica overlap com os nomes
     dos grupos e categorias.
  3. Retorna o melhor match com score de confiança.

Por que assim:
  - Grupos têm nomes semânticos claros (CERVEJAS, REFRIGERANTE, BISCOITO DOCE)
    que aparecem naturalmente nas descrições de EFD expandidas.
  - Categorias são mais específicas e nem sempre coincidem com tokens isolados,
    por isso usamos grupos como âncora principal.
  - Score é baseado em proporção de tokens em comum (Jaccard simples).
  - Fase 2: substituir por RapidFuzz; Fase 3: substituir por embeddings.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from sqlalchemy.orm import Session


@dataclass
class ResultadoCategorizacao:
    categoria_id:    Optional[int]
    categoria_nome:  Optional[str]
    grupo_id:        Optional[int]
    grupo_nome:      Optional[str]
    departamento_id: Optional[int]
    departamento_nome: Optional[str]
    score:           float  # 0.0 a 1.0


# ── Cache em memória ──────────────────────────────────────────────────────────
# Armazena o índice após a primeira carga para não ir ao banco a cada produto.

_INDICE_GRUPOS:     list[dict] | None = None
_INDICE_CATEGORIAS: list[dict] | None = None


def _normalizar(texto: str) -> set[str]:
    """Tokeniza e normaliza: remove acentos, minúsculas, retorna set de tokens."""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^A-Za-z0-9\s]", " ", texto).lower()
    return set(texto.split())


def carregar_indice(session: Session) -> None:
    """
    Popula os índices em memória a partir do banco.
    Deve ser chamado uma vez por processo (ou por sessão no Streamlit).
    """
    global _INDICE_GRUPOS, _INDICE_CATEGORIAS

    from app.models.categoria import Grupo, Categoria, Departamento

    grupos = (
        session.query(Grupo, Departamento)
        .join(Departamento, Grupo.departamento_id == Departamento.id)
        .all()
    )
    _INDICE_GRUPOS = [
        {
            "grupo_id":        g.id,
            "grupo_nome":      g.descricao,
            "departamento_id": d.id,
            "departamento_nome": d.descricao,
            "tokens":          _normalizar(g.descricao),
        }
        for g, d in grupos
    ]

    categorias = (
        session.query(Categoria, Grupo, Departamento)
        .join(Grupo, Categoria.grupo_id == Grupo.id)
        .join(Departamento, Grupo.departamento_id == Departamento.id)
        .all()
    )
    _INDICE_CATEGORIAS = [
        {
            "categoria_id":    c.id,
            "categoria_nome":  c.descricao,
            "grupo_id":        g.id,
            "grupo_nome":      g.descricao,
            "departamento_id": d.id,
            "departamento_nome": d.descricao,
            "tokens":          _normalizar(c.descricao),
        }
        for c, g, d in categorias
    ]


# Vocabulário de tipo de produto → grupo canônico.
# Verificado ANTES do hortifruti para evitar que "MACA" em "VINAGRE DE MACA"
# classifique erroneamente como FRUTAS.
# Chave: token ou bigrama que identifica o tipo do produto (maiúsculas).
# Valor: nome exato do grupo no banco.
_VOCAB_TIPO_PRODUTO: dict[str, str] = {
    # Limpeza (itens que _VOCAB_CATEGORIA já cobre ficam como fallback de grupo)
    "LAVA ROUPA":       "LIMPEZA PARA ROUPAS",
    "LAVA-ROUPA":       "LIMPEZA PARA ROUPAS",
    # Higiene
    "SABONETE":     "SABONETES",
    "DESODORANTE":  "DESODORANTES E COLONIAS",
    "ENXAGUANTE":   "HIGIENE BUCAL",
    # Mercearia salgada
    "VINAGRE":      "VINAGRES",
    "AZEITE":       "AZEITES",
    "TEMPERO":      "TEMPEROS E MOLHOS",
    "MOLHO":        "TEMPEROS E MOLHOS",
    "MACARRAO":     "MASSAS E SOPAS",
    "MASSA":        "MASSAS E SOPAS",
    "CONSERVA":     "CONSERVAS E ENLATADOS",
    "MILHO ENLATADO": "CONSERVAS E ENLATADOS",
    # Mercearia doce
    "CHOCOLATE":    "CHOCOLATES",
    "BISCOITO":     "BISCOITO DOCE",
    "MEL":          "MEL E MELADOS",
    "QUEIJO":       "LATICINIOS",
    # Proteínas
    "FRANGO":       "AVES",
    "BOVINO":       "BOVINO",
    "SUINO":        "SUINO",
    # Bebidas
    "REFRIGERANTE": "REFRIGERANTE",
    "CERVEJA":      "CERVEJAS",
    "VINHO":        "VINHO",
    "SUCO":         "SUCOS",
    "AGUA":         "AGUAS",
    # Commodities
    "ARROZ":        "ARROZ",
    "FEIJAO":       "FEIJAO",
    "ACUCAR":       "ACUCAR",
    "FARINHA":      "FARINACEOS",
    "FARINHA DE TRIGO": "FARINHA DE TRIGO",
    "SAL":          "SAL",
    "OLEO":         "OLEO",
    "LEITE":        "LEITE",
    "CAFE":         "MATINAIS",
    "CHA":          "MATINAIS",
}

# Vocabulário de hortifruti: produto → grupo canônico (nome exato no banco)
# Necessário porque os grupos se chamam LEGUMES/VERDURAS/FRUTAS e os produtos
# (CENOURA, PEPINO, ALFACE) nunca aparecem nesses nomes.
_VOCAB_HORTIFRUTI: dict[str, str] = {
    # Legumes
    "CENOURA": "LEGUMES", "BETERRABA": "LEGUMES", "BATATA": "LEGUMES",
    "AIPIM": "LEGUMES", "MANDIOCA": "LEGUMES", "INHAME": "LEGUMES",
    "CHUCHU": "LEGUMES", "ABOBRINHA": "LEGUMES", "ABOBORA": "LEGUMES",
    "PEPINO": "LEGUMES", "JILÓ": "LEGUMES", "JILO": "LEGUMES",
    "QUIABO": "LEGUMES", "PIMENTAO": "LEGUMES", "BERINJELA": "LEGUMES",
    "VAGEM": "LEGUMES", "ERVILHA": "LEGUMES", "MILHO": "LEGUMES",
    "TOMATE": "LEGUMES", "CEBOLA": "LEGUMES", "ALHO": "LEGUMES",
    "BATATA DOCE": "LEGUMES", "BATATA INGLESA": "LEGUMES",
    # Verduras
    "ALFACE": "VERDURAS", "COUVE": "VERDURAS", "BROCOLIS": "VERDURAS",
    "COUVE FLOR": "VERDURAS", "REPOLHO": "VERDURAS", "ESPINAFRE": "VERDURAS",
    "RUCULA": "VERDURAS", "AGRIAO": "VERDURAS", "SALSINHA": "VERDURAS",
    "CEBOLINHA": "VERDURAS", "COENTRO": "VERDURAS",
    # Frutas
    "BANANA": "FRUTAS", "MACA": "FRUTAS", "LARANJA": "FRUTAS",
    "LIMAO": "FRUTAS", "ABACAXI": "FRUTAS", "MAMAO": "FRUTAS",
    "MELANCIA": "FRUTAS", "MELAO": "FRUTAS", "UVA": "FRUTAS",
    "MORANGO": "FRUTAS", "PERA": "FRUTAS", "MANGA": "FRUTAS",
    "GOIABA": "FRUTAS", "MARACUJA": "FRUTAS", "COCO": "FRUTAS",
    "ABACATE": "FRUTAS", "KIWI": "FRUTAS",
    # Ovos
    "OVO": "OVOS", "OVOS": "OVOS",
}

# Vocabulário de categoria exata: termo → (nome_categoria, grupo_preferido|None).
# Usado quando queremos classificar no nível mais granular (Dep→Grp→Cat).
# Verificado ANTES do vocabulário de tipo de produto.
# Chave: token, bigrama ou trigrama em maiúsculas.
# Valor: (nome exato da categoria, nome do grupo para desambiguar duplicatas ou None).
_VOCAB_CATEGORIA: dict[str, tuple[str, str | None]] = {
    # ══ LIMPEZA PARA ROUPAS ══════════════════════════════════════════
    "AGUA SANITARIA":   ("AGUA SANITARIA",              None),
    "ALVEJANTE":        ("ALVEJANTES E CLORO",           None),
    "ALVEJANTES":       ("ALVEJANTES E CLORO",           None),
    "SABAO EM PO":      ("SABAO EM PO",                  None),
    "SABAO LIQUIDO":    ("SABAO LIQUIDO",                None),
    "SABAO EM BARRA":   ("SABAO EM BARRA E PASTA",       None),
    "TIRA MANCHAS":     ("CORANTES, TIRA MANCHAS, GOMA", None),
    "AMACIANTE":        ("AMACIANTE DE ROUPA",           None),
    # ══ LIMPEZA DE COZINHA ═══════════════════════════════════════════
    "DETERGENTE":       ("DETERGENTES LIQUIDOS E GEL",   None),
    "ESPONJA":          ("ESPONJAS",                     None),
    "ESPONJA ACO":      ("ESPONJAS",                     None),
    "DESENGORDURANTE":  ("DESENGORDURANTES",             None),
    "SAPONACEO":        ("SAPONACEOS PO",                None),
    # ══ LIMPEZA DE CASA ══════════════════════════════════════════════
    "DESINFETANTE":     ("DESINFETANTES ATE 500ML",      None),
    "MULTIUSO":         ("MULTIUSO",                     None),
    "LIMPA VIDRO":      ("LIMPA VIDROS",                 None),
    "LIMPA VIDROS":     ("LIMPA VIDROS",                 None),
    "PALHA DE ACO":     ("PALHA DE ACO",                 None),
    "ODORIZADOR":       ("ODORIZADOR DE AMBIENTE",       None),
    # ══ LIMPEZA DE PISOS ═════════════════════════════════════════════
    "CERA LIQUIDA":     ("CERAS LIQUIDAS",               None),
    # ══ INSETICIDAS ══════════════════════════════════════════════════
    "INSETICIDA":       ("INSETICIDA DOMESTICO AEROSOL", None),
    # ══ CONGELADOS — PERECÍVEIS DO AUTOSERVIÇO ═══════════════════════
    "ACAI":             ("SORVETEs / ACAI",              "CONGELADOS"),
    "SORVETE":          ("SORVETEs / ACAI",              "CONGELADOS"),
    "POLPA DE FRUTAS":  ("POLPA DE FRUTAS",              "CONGELADOS"),
    "POLPA":            ("POLPA DE FRUTAS",              "CONGELADOS"),
    "PAO DE QUEIJO":    ("PAO DE QUEIJO",                "CONGELADOS"),
    "LASANHA":          ("LASANHA",                      "CONGELADOS"),
    "PIZZA":            ("PIZZA / HAMBURGUER",           "CONGELADOS"),
    "HAMBURGUER":       ("PIZZA / HAMBURGUER",           "CONGELADOS"),
    "EMPANADO":         ("EMPANADOS",                    "CONGELADOS"),
    "EMPANADOS":        ("EMPANADOS",                    "CONGELADOS"),
    "PICOLE":           ("PICOLÉ / GELADINHO / SACOLE",  "CONGELADOS"),
    "GELADINHO":        ("PICOLÉ / GELADINHO / SACOLE",  "CONGELADOS"),
    "BATATA CONGELADA": ("BATATA CONGELADA",             "CONGELADOS"),
    "BATATA PRE FRITA": ("BATATA CONGELADA",             "CONGELADOS"),
    "PRE FRITA":        ("BATATA CONGELADA",             "CONGELADOS"),
    # ══ LATICÍNIOS ═══════════════════════════════════════════════════
    "IOGURTE":          ("IOGURTES TRADICIONAL",         "LATICINIOS"),
    "REQUEIJAO":        ("REQUEIJAO",                    "LATICINIOS"),
    "MANTEIGA":         ("MANTEIGA",                     "LATICINIOS"),
    "MARGARINA":        ("MARGARINA E CREME VEGETAL",    "LATICINIOS"),
    "CREME DE LEITE":   ("CREME DE LEITE",              "CULINARIA DOCE"),
    "QUEIJO MUSSARELA": ("QUEIJO MUSSARELA",             "LATICINIOS"),
    "LEITE FERMENTADO": ("LEITE FERMENTADO",             "LATICINIOS"),
    "BEBIDA LACTEA":    ("BEBIDAS LACTEAS",              "LATICINIOS"),
    "CHANTILLY":        ("CHANTILLY",                    "LATICINIOS"),
    # ══ FRIOS / FATIADOS ═════════════════════════════════════════════
    "PRESUNTO":         ("PRESUNTO",                     "FRIOS / FATIADOS"),
    "MORTADELA":        ("MORTADELA",                    "FRIOS / FATIADOS"),
    "MUSSARELA":        ("MUSSARELA",                    "FRIOS / FATIADOS"),
    "APRESUNTADO":      ("APRESUNTADO",                  "FRIOS / FATIADOS"),
    "SALAME":           ("MORTADELA/SALAME",             "FRIAMBRERIA"),
    # ══ BEBIDAS — CERVEJAS ═══════════════════════════════════════════
    "CERVEJA LATA":     ("CERVEJA LATA",                 None),
    "CERVEJA LONG":     ("CERVEJA LONG NECK",            None),
    "CERVEJA GARRAFA":  ("CERVEJA GARRAFA",              None),
    # ══ BEBIDAS — REFRIGERANTE ═══════════════════════════════════════
    "REFRIGERANTE COLA":    ("REFRIGERANTE COLA",        None),
    "REFRIGERANTE GUARANA": ("REFRIGERANTE GUARANA",     None),
    "AGUA TONICA":      ("AGUA TONICA",                  None),
    # ══ BEBIDAS — ÁGUAS ══════════════════════════════════════════════
    "AGUA DE COCO":     ("AGUA DE COCO",                 None),
    "AGUA MINERAL":     ("AGUA MINERAL ATE 2,5 L",       None),
    "AGUA SABORIZADA":  ("AGUA SABORIZADA",              None),
    "AGUA GASEIFICADA": ("AGUA GASEIFICADA",             None),
    # ══ BEBIDAS — OUTRAS ═════════════════════════════════════════════
    "ENERGETICO":       ("BEBIDAS ENERGETICAS",          None),
    "ISOTONICO":        ("ISOTONICOS",                   None),
    "CHA PRONTO":       ("CHAS PRONTOS",                 None),
    "BEBIDA VEGETAL":   ("BEBIDA VEGETAL",               None),
    # ══ BEBIDAS — SUCOS ══════════════════════════════════════════════
    "SUCO INTEGRAL":    ("SUCO INTEGRAL",                None),
    "SUCO CONCENTRADO": ("SUCO CONCENTRADO",             None),
    "REFRESCO EM PO":   ("REFRESCO EM PO",               None),
    "REFRESCO":         ("REFRESCO EM PO",               None),
    # ══ BEBIDAS — DESTILADOS ═════════════════════════════════════════
    "WHISKY":           ("WHISKY",                       None),
    "VODKA":            ("VODKA",                        None),
    "GIN":              ("GIN",                          None),
    "RUM":              ("RUM",                          None),
    "TEQUILA":          ("TEQUILA",                      None),
    "CACHACA":          ("AGUARDENTES",                  None),
    "AGUARDENTE":       ("AGUARDENTES",                  None),
    # ══ BEBIDAS — VINHO ══════════════════════════════════════════════
    "ESPUMANTE":        ("ESPUMANTES/FRISANTES/CHAMPAGNE", None),
    "CHAMPAGNE":        ("ESPUMANTES/FRISANTES/CHAMPAGNE", None),
    "VINHO TINTO":      ("VINHO TINTO",                  None),
    "VINHO BRANCO":     ("VINHO BRANCO",                 None),
    # ══ COMMODITIES — LEITE ══════════════════════════════════════════
    "LEITE INTEGRAL":      ("LEITE INTEGRAL",            None),
    "LEITE DESNATADO":     ("LEITE DESNATADO",           None),
    "LEITE SEMIDESNATADO": ("LEITE SEMIDESNATADO",       None),
    "LEITE SEM LACTOSE":   ("LEITE SEM LACTOSE",         None),
    "LEITE EM PO":         ("LEITE EM PO",               None),
    # ══ COMMODITIES — ARROZ ══════════════════════════════════════════
    "ARROZ INTEGRAL":    ("ARROZ INTEGRAL",              None),
    "ARROZ PARBOILIZADO":("ARROZ PARBOILIZADO",          None),
    # ══ COMMODITIES — FEIJÃO ═════════════════════════════════════════
    "FEIJAO CARIOCA":   ("FEIJAO CARIOCA",               None),
    "FEIJAO PRETO":     ("FEIJAO PRETO",                 None),
    "FEIJAO BRANCO":    ("FEIJAO BRANCO",                None),
    # ══ COMMODITIES — ÓLEO ═══════════════════════════════════════════
    "OLEO DE SOJA":     ("OLEO DE SOJA",                 None),
    "OLEO DE MILHO":    ("OLEO DE MILHO",                None),
    "OLEO DE CANOLA":   ("OLEO DE CANOLA",               None),
    "OLEO DE COCO":     ("OLEO DE COCO",                 None),
    # ══ MERCEARIA DOCE — MATINAIS ════════════════════════════════════
    "ACHOCOLATADO":     ("ACHOCOLATADO EM PO",            "MATINAIS"),
    "CAFE EM PO":       ("CAFE EM PO",                   None),
    "CAFE SOLUVEL":     ("CAFE SOLUVEL",                 None),
    "CAFE CAPSULA":     ("CAFE E OUTRAS PREPARACOES EM CAPSULA", None),
    "CAPPUCCINO":       ("CAPPUCCINO EM PO",             None),
    "CHIMARRAO":        ("CHIMARRAO E TERERE",           None),
    "TERERE":           ("CHIMARRAO E TERERE",           None),
    # ══ MERCEARIA DOCE — BISCOITOS ═══════════════════════════════════
    "BISCOITO RECHEADO":("BISCOITO RECHEADO",            None),
    "BISCOITO MAIZENA": ("BISCOITO MAIZENA",             None),
    "BISCOITO MARIA":   ("BISCOITO MARIA",               None),
    "WAFER":            ("WAFER",                        "BISCOITO DOCE"),
    "ROSQUINHA":        ("ROSQUINHAS E SEQUILHOS",       None),
    "SEQUILHO":         ("ROSQUINHAS E SEQUILHOS",       None),
    "COOKIE":           ("COOKIES",                      None),
    "COOKIES":          ("COOKIES",                      None),
    "CREAM CRACKER":    ("CREAM CRACKER",                None),
    # ══ MERCEARIA DOCE — CHOCOLATES ══════════════════════════════════
    "CHOCOLATE BARRA":  ("CHOCOLATE EM BARRAS",          None),
    "BOMBOM":           ("BOMBONS PACOTE",               None),
    # ══ MERCEARIA DOCE — CULINÁRIA ═══════════════════════════════════
    "LEITE CONDENSADO": ("LEITE CONDENSADO",             None),
    "COCO RALADO":      ("COCO RALADO",                  None),
    "LEITE DE COCO":    ("LEITE DE COCO",                None),
    "CHOCOLATE EM PO":  ("CHOCOLATES EM PO",             None),
    "FERMENTO":         ("FERMENTO QUIMICO E COALHO",    "CULINARIA DOCE"),
    "AMIDO DE MILHO":   ("AMIDO DE MILHO",               None),
    "MISTURA BOLO":     ("MISTURAS PARA BOLOS E SALGADOS", None),
    # ══ MERCEARIA DOCE — SOBREMESAS ══════════════════════════════════
    "GELATINA":         ("GELATINA EM PO",               None),
    "PUDIM":            ("PO P/ PUDIM, FLAN, MARIA MOLE", None),
    "DOCE DE LEITE":    ("DOCES DE LEITE",               None),
    "GELEIA":           ("TRADICIONAL",                  "GELEIAS"),
    # ══ MERCEARIA DOCE — SALGADINHOS ═════════════════════════════════
    "SALGADINHO":         ("SALGADINHOS SABORES",        None),
    "BATATA PALHA":       ("BATATA PALHA",               None),
    "BATATA FRITA":       ("BATATA FRITA",               None),
    "ELMA CHIPS":         ("BATATA FRITA",               None),
    "BATATA ELMA CHIPS":  ("BATATA FRITA",               None),
    "AMENDOIM":         ("AMENDOIM",                     "SALGADINHO"),
    "PIPOCA":           ("PIPOCA EM GERAL",              None),
    # ══ MERCEARIA DOCE — GULOSEIMAS ══════════════════════════════════
    "BALA":             ("BALAS COMUM",                  None),
    "CHICLETE":         ("GOMA DE MASCAR",               None),
    "PIRULITO":         ("PIRULITOS",                    None),
    "MARSHMALLOW":      ("MARSHMALLOWS",                 None),
    # ══ MERCEARIA SALGADA — CONSERVAS ════════════════════════════════
    "AZEITONA":         ("AZEITONAS CONSERVA",           None),
    "PALMITO":          ("PALMITO CONSERVA",             None),
    "MILHO VERDE":      ("MILHO VERDE CONSERVA",         None),
    "SARDINHA":         ("SARDINHA CONSERVA",             None),
    "ATUM":             ("ATUM CONSERVA",                None),
    "FEIJOADA ENLATADA":("FEIJOADA ENLATADA",            None),
    # ══ MERCEARIA SALGADA — TEMPEROS E MOLHOS ════════════════════════
    "EXTRATO DE TOMATE":("EXTRATO DE TOMATE",            None),
    "MOLHO DE TOMATE":  ("MOLHOS E POLPAS TOMATE",       None),
    "CATCHUP":          ("CATCHUP",                      None),
    "KETCHUP":          ("CATCHUP",                      None),
    "MOSTARDA":         ("MOSTARDA",                     None),
    "MAIONESE":         ("MAIONESE",                     None),
    "MOLHO DE PIMENTA": ("MOLHO DE PIMENTA",             None),
    "MOLHO DE SOJA":    ("MOLHO DE SOJA",                None),
    "MOLHO INGLES":     ("MOLHO INGLES E OUTROS",        None),
    "CALDO TABLETE":    ("CALDO TABLETE E PO",           None),
    # ══ MERCEARIA SALGADA — MASSAS ═══════════════════════════════════
    "MACARRAO INSTANTANEO": ("MACARRAO INSTANTANEO",     None),
    # ══ MERCEARIA SALGADA — AZEITES ══════════════════════════════════
    "AZEITE EXTRA VIRGEM":  ("AZEITE EXTRA VIRGEM",      None),
    # ══ MERCEARIA SALGADA — VINAGRES ═════════════════════════════════
    "VINAGRE DE MACA":  ("VINAGRE DE MACA",              None),
    # ══ MERCEARIA SALGADA — FARINÁCEOS ═══════════════════════════════
    "FARINHA DE MANDIOCA":  ("FARINHA DE MANDIOCA",       None),
    "FAROFA":           ("FAROFAS PRONTAS",              None),
    "POLVILHO":         ("POLVILHO",                     None),
    # ══ HIGIENE BUCAL ════════════════════════════════════════════════
    "CREME DENTAL":     ("CREME DENTAL",                 None),
    "PASTA DENTAL":     ("CREME DENTAL",                 None),
    "ESCOVA DENTAL":    ("ESCOVAS DENTAL",               None),
    "FIO DENTAL":       ("FIO DENTAL",                   None),
    "FITA DENTAL":      ("FIO DENTAL",                   None),
    "ENXAGUANTE BUCAL": ("ANTISSÉPTICO BUCAL",           None),
    "ANTISSEPTICO BUCAL":("ANTISSÉPTICO BUCAL",          None),
    # ══ PRODUTOS CAPILARES ═══════════════════════════════════════════
    "SHAMPOO":          ("SHAMPOO",                      "PRODUTOS CAPILARES"),
    "CONDICIONADOR":    ("CONDICIONADOR",                "PRODUTOS CAPILARES"),
    "CREME PENTEAR":    ("CREME PARA PENTEAR",           None),
    "TINTURA":          ("TINTURA / DESCOLORANTES PARA CABELO", None),
    # ══ DESODORANTES ═════════════════════════════════════════════════
    "DESODORANTE AEROSOL": ("DESODORANTE AEROSOL",       None),
    "DESODORANTE ROLL": ("DESODORANTE ROLLON",           None),
    "DESODORANTE ROLLON":("DESODORANTE ROLLON",          None),
    # ══ SABONETES ════════════════════════════════════════════════════
    "SABONETE LIQUIDO": ("SABONETES LÍQUIDOS",           None),
    "SABONETE BARRA":   ("SABONETES BARRA",              None),
    "SABONETE INTIMO":  ("SABONETE INTIMO",              None),
    # ══ PAPEL HIGIÊNICO ═════════════════════════════════════════════
    "PAPEL HIGIENICO":  ("PAP. HIG. FOLHA DUPLAS",       None),
    # ══ PROTETOR SOLAR ═══════════════════════════════════════════════
    "PROTETOR SOLAR":   ("PROTETOR SOLAR",               None),
    "REPELENTE":        ("REPELENTES",                   None),
    # ══ ABSORVENTES ══════════════════════════════════════════════════
    "ABSORVENTE":       ("ABSORVENTE EXTERNO",           "ABSORVENTES"),
    # ══ SEÇÃO INFANTIL ═══════════════════════════════════════════════
    "FRALDA":           ("FRALDAS DESCARTÁVEIS PARA BEBĘ", "SECAO INFANTIL"),
    "LENCO UMEDECIDO":  ("LENCOS UMEDECIDOS",            "SECAO INFANTIL"),
    # ══ APERITIVOS ═══════════════════════════════════════════════════
    "APERITIVO":          ("APERITIVOS EM GERAL",      "EMPORIO GRANEL"),
    # ══ PAPELARIA ════════════════════════════════════════════════════
    "APONTADOR":          ("APONTADORES EM GERAL",     "ARTIGOS PARA PAPELARIA E ARMARINHO"),
    # ══ CAPILARES — ESPECÍFICOS ══════════════════════════════════════
    "ATIVADOR DE CACHOS": ("CREME PARA PENTEAR",       "PRODUTOS CAPILARES"),
    # ══ MERCEARIA DOCE — CEREAIS ═════════════════════════════════════
    "AVEIA":              ("CEREAIS",                  "MATINAIS"),
    # ══ BARBEARIA ════════════════════════════════════════════════════
    "APARELHO DE BARBEAR": ("APARELHOS DESCARTÁVEIS",    "BARBEARIA"),
    "APARELHO BARBEAR":    ("APARELHOS DESCARTÁVEIS",    "BARBEARIA"),
    "LAMINA BARBEAR":      ("LAMINAS (REFIL)",            "BARBEARIA"),
    "CREME BARBEAR":       ("CREMES E LOCŐES P/BARBEAR", "BARBEARIA"),
    # ══ ESTÉTICA ═════════════════════════════════════════════════════
    "ESMALTE":          ("ESMALTE PARA UNHA",            None),
    # ══ DESCARTÁVEIS / BAZAR ═════════════════════════════════════════
    "PAPEL TOALHA":     ("PAPEL TOALHA",                 None),
    "PAPEL ALUMINIO":   ("PAPEL ALUMINIO",               None),
    "GUARDANAPO":       ("GURDANAPO DE PAPEL",           None),
    "FILME PVC":        ("FILME PVC",                    None),
    "SACO PARA LIXO":   ("SACOS PARA LIXO",              None),
    "SACO DE LIXO":     ("SACOS PARA LIXO",              None),
    # ══ UTENSÍLIOS LIMPEZA ═══════════════════════════════════════════
    "VASSOURA":         ("VASSOURAS",                    None),
    "RODO":             ("RODOS",                        None),
    # ══ AÇOUGUE ══════════════════════════════════════════════════════
    "LINGUICA":         ("LINGUICA GRANEL ATENDIMENTO",  None),
    "SALSICHA":         ("SALSICHA GRANEL ATENDIMENTO",  None),
    # ══ NUTRIÇÃO INFANTIL ════════════════════════════════════════════
    "PAPINHA":          ("PAPINHAS",                     None),
    # ══ TABACARIA ════════════════════════════════════════════════════
    "CIGARRO":          ("CIGARRO EM GERAL",             None),
    # ══ PET SHOP ═════════════════════════════════════════════════════
    "RACAO":            ("ALIMENTO PARA CAES",           "RACAO E PET SHOP"),
    # ══ CARVÃO / CHURRASCO ═══════════════════════════════════════════
    "CARVAO":           ("CARVAO",                       None),
    # ══ PADARIA ══════════════════════════════════════════════════════
    "PAO FRANCES":      ("PAO FRANCES",                  None),
    "PAO DE FORMA":     ("PAO DE FORMA COMUM",           None),
}


def _match_por_categoria_nome(
    categoria_nome: str, session: Session, score: float,
    grupo_preferido: str | None = None,
) -> ResultadoCategorizacao:
    """
    Busca categoria pelo nome exato e retorna ResultadoCategorizacao preenchido.
    Se `grupo_preferido` for informado, prioriza a categoria que pertence a esse grupo
    (útil quando há duplicatas de nome em grupos diferentes, ex: PAO DE QUEIJO).
    """
    global _INDICE_CATEGORIAS
    if _INDICE_CATEGORIAS is None:
        carregar_indice(session)
    candidatos = [
        item for item in _INDICE_CATEGORIAS
        if item["categoria_nome"].upper() == categoria_nome.upper()
    ]
    if not candidatos:
        return _vazio()
    # Prioriza o grupo preferido quando há ambiguidade
    if grupo_preferido:
        preferred = [c for c in candidatos if c["grupo_nome"].upper() == grupo_preferido.upper()]
        if preferred:
            candidatos = preferred
    item = candidatos[0]
    return ResultadoCategorizacao(
        categoria_id=item["categoria_id"],
        categoria_nome=item["categoria_nome"],
        grupo_id=item["grupo_id"],
        grupo_nome=item["grupo_nome"],
        departamento_id=item["departamento_id"],
        departamento_nome=item["departamento_nome"],
        score=score,
    )


def categorizar(
    descricao: str,
    session: Session,
    threshold: float = 0.30,
) -> ResultadoCategorizacao:
    """
    Classifica uma descrição de produto na hierarquia departamento/grupo/categoria.

    Retorna ResultadoCategorizacao com os IDs e nomes do melhor match.
    Se score < threshold, retorna None nos campos (produto vai para revisão).

    Exemplos esperados (após expansão das abreviações):
      "REFRIGERANTE COCA COLA PET 2L"  → grupo REFRIGERANTE / dept BEBIDAS
      "CERVEJA SKOL LATA 350ML"        → grupo CERVEJAS / dept BEBIDAS
      "DETERGENTE LIQUIDO YPE 500ML"   → grupo LIMPEZA DE COZINHA / dept LIMPEZA
      "LEITE INTEGRAL 1L"              → grupo LEITE / dept COMMODITIES
      "BISCOITO RECHEADO 140G"         → grupo BISCOITO DOCE / dept MERCEARIA DOCE
    """
    global _INDICE_GRUPOS, _INDICE_CATEGORIAS

    if _INDICE_GRUPOS is None:
        carregar_indice(session)

    tokens_desc = _normalizar(descricao)
    if not tokens_desc:
        return _vazio()

    palavras = descricao.upper().split()

    # 0. Vocabulário de categoria exata (maior prioridade — resolve até o 3º nível)
    #    Trigramas → bigramas → unigramas para evitar matches parciais ambíguos
    for size in (3, 2, 1):
        for i in range(len(palavras) - size + 1):
            chave = " ".join(palavras[i:i + size])
            if chave in _VOCAB_CATEGORIA:
                cat_nome, grp_pref = _VOCAB_CATEGORIA[chave]
                return _match_por_categoria_nome(cat_nome, session, score=0.98,
                                                 grupo_preferido=grp_pref)

    # 0a. Vocabulário de tipo de produto (evita conflitos como MACA → FRUTAS em VINAGRE DE MACA)
    #     Bigramas primeiro (ex: "FARINHA DE TRIGO" > "FARINHA")
    for i in range(len(palavras) - 1):
        bigrama = f"{palavras[i]} {palavras[i+1]}"
        if bigrama in _VOCAB_TIPO_PRODUTO:
            return _match_por_grupo_nome(_VOCAB_TIPO_PRODUTO[bigrama], session, score=0.95)
    for token in palavras:
        if token in _VOCAB_TIPO_PRODUTO:
            return _match_por_grupo_nome(_VOCAB_TIPO_PRODUTO[token], session, score=0.95)

    # 0b. Vocabulário de hortifruti (bigramas primeiro: BATATA DOCE > BATATA)
    for i in range(len(palavras) - 1):
        bigrama = f"{palavras[i]} {palavras[i+1]}"
        if bigrama in _VOCAB_HORTIFRUTI:
            return _match_por_grupo_nome(_VOCAB_HORTIFRUTI[bigrama], session, score=0.90)
    for token in palavras:
        if token in _VOCAB_HORTIFRUTI:
            return _match_por_grupo_nome(_VOCAB_HORTIFRUTI[token], session, score=0.90)

    # 1. Tenta match em categorias (mais específico)
    melhor_cat = _melhor_match(tokens_desc, _INDICE_CATEGORIAS)
    if melhor_cat and melhor_cat["score"] >= threshold:
        d = melhor_cat
        return ResultadoCategorizacao(
            categoria_id=d["categoria_id"],
            categoria_nome=d["categoria_nome"],
            grupo_id=d["grupo_id"],
            grupo_nome=d["grupo_nome"],
            departamento_id=d["departamento_id"],
            departamento_nome=d["departamento_nome"],
            score=d["score"],
        )

    # 2. Fallback: match em grupos (âncora semântica mais confiável)
    melhor_grp = _melhor_match(tokens_desc, _INDICE_GRUPOS)
    if melhor_grp and melhor_grp["score"] >= threshold:
        d = melhor_grp
        return ResultadoCategorizacao(
            categoria_id=None,
            categoria_nome=None,
            grupo_id=d["grupo_id"],
            grupo_nome=d["grupo_nome"],
            departamento_id=d["departamento_id"],
            departamento_nome=d["departamento_nome"],
            score=d["score"],
        )

    return _vazio()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _melhor_match(tokens_desc: set[str], indice: list[dict]) -> dict | None:
    """
    Retorna o item do índice com maior score de cobertura.

    Score = intersecao / len(tokens_item)
    Regra anti-falso-positivo: para itens com 2+ tokens, exige intersecao >= 2.
    Isso evita que um único token ambíguo ("BARRA", "ROSA", "CRISTAL")
    cause um match errado com categorias como "SABONETE EM BARRA" ou "SAL ROSA".
    """
    melhor = None
    melhor_score = 0.0
    for item in indice:
        tokens_item = item["tokens"]
        if not tokens_item:
            continue
        intersecao = len(tokens_desc & tokens_item)
        if intersecao == 0:
            continue
        # Anti falso-positivo: itens multi-token exigem ao menos 2 matches
        if len(tokens_item) >= 2 and intersecao < 2:
            continue
        score = intersecao / len(tokens_item)
        if score > melhor_score:
            melhor_score = score
            melhor = {**item, "score": round(score, 4)}
    return melhor


def _match_por_grupo_nome(
    grupo_nome: str, session: Session, score: float
) -> ResultadoCategorizacao:
    """Busca grupo pelo nome exato e retorna ResultadoCategorizacao preenchido."""
    global _INDICE_GRUPOS
    if _INDICE_GRUPOS is None:
        carregar_indice(session)
    for item in _INDICE_GRUPOS:
        if item["grupo_nome"].upper() == grupo_nome.upper():
            return ResultadoCategorizacao(
                categoria_id=None,
                categoria_nome=None,
                grupo_id=item["grupo_id"],
                grupo_nome=item["grupo_nome"],
                departamento_id=item["departamento_id"],
                departamento_nome=item["departamento_nome"],
                score=score,
            )
    return _vazio()


def _vazio() -> ResultadoCategorizacao:
    return ResultadoCategorizacao(
        categoria_id=None, categoria_nome=None,
        grupo_id=None, grupo_nome=None,
        departamento_id=None, departamento_nome=None,
        score=0.0,
    )


def invalidar_cache() -> None:
    """Limpa o cache — chamar ao salvar novas categorias no banco."""
    global _INDICE_GRUPOS, _INDICE_CATEGORIAS
    _INDICE_GRUPOS = None
    _INDICE_CATEGORIAS = None
