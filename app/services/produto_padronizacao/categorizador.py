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


def _normalizar_lista(texto: str) -> list[str]:
    """Tokeniza e normaliza preservando ordem: remove acentos, minúsculas, lista de tokens."""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^A-Za-z0-9\s]", " ", texto).lower()
    return texto.split()


def _normalizar(texto: str) -> set[str]:
    """Tokeniza e normaliza: remove acentos, minúsculas, retorna set de tokens."""
    return set(_normalizar_lista(texto))


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
    "CALDO":        "TEMPEROS E MOLHOS",
    # SHOYU movido para _VOCAB_CATEGORIA (categoria específica MOLHO DE SOJA)
    "MACARRAO":     "MASSAS E SOPAS",
    "MASSA":        "MASSAS E SOPAS",
    "CONSERVA":     "CONSERVAS E ENLATADOS",
    "MILHO ENLATADO": "CONSERVAS E ENLATADOS",
    # Mercearia doce
    "CHOCOLATE":    "CHOCOLATES",
    "BISCOITO":     "BISCOITO DOCE",
    "MEL":          "MEL E MELADOS",
    "QUEIJO":       "LATICINIOS",
    # Proteínas e açougue
    "FRANGO":       "AVES",
    "BOVINO":       "BOVINO",
    "SUINO":        "SUINO",
    "CARNE SUINA":  "SUINO",           # bigrama: "CARNE SUINA BISTECA KG"
    "FILE PEITO":   "CONGELADOS",      # bigrama: "FILE DE PEITO PERDIGAO" (congelados no supermercado)
    "PEIXE":        "PEIXES",          # "PEIXE TILAPIA GARCIA FILE 400G"
    # Bebidas
    "REFRIGERANTE": "REFRIGERANTE",
    "CERVEJA":      "CERVEJAS",
    "VINHO":        "VINHO",
    "SUCO":         "SUCOS",
    "AGUA":         "AGUAS",
    "COQUETEL":     "DESTILADOS",      # coquetel catuaba/ice syn → destilados
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
    "CEREAL MATINAL": "MATINAIS",      # bigrama: "CEREAL MATINAL NESTLE NESCAU"
    # Bazar geral
    "BACIA":        "UTILIDADES DA COZINHA",
    "LIMPADOR":     "LIMPEZA DE CASA",       # "LIMPADOR PERFUMADO UAU / CIF"
    "LAMPADA":      "FERRAMENTAS E ACESSORIOS",  # LÂMPADAS tem acento no banco
    "LUVA":         "UTENSILIOS PARA LIMPEZA",   # LUVA LATEX / LUVA LIMPEZA
    # Frutas secas/oleaginosas — categoria tem acento incomum no banco; usa grupo
    "CASTANHA":     "FRUTAS SECAS",             # CASTANHA DO PARA, CASTANHA DE CAJU...
    "AMENDOA":      "FRUTAS SECAS",             # AMENDOA NATURAL / FATIADA
    "NOZ":          "FRUTAS SECAS",             # NOZ PECAN, NOZ MOSCADA...
    "NOZES":        "FRUTAS SECAS",
    # Seção Infantil — "FRALDAS DESCARTÁVEIS PARA BEBÊ" tem acento incomum no banco;
    # usar grupo evita mismatch por diferença de caractere especial (Ę vs Ê)
    "FRALDA":       "SECAO INFANTIL",
    "FRALDINHA":    "SECAO INFANTIL",
    "MAMADEIRA":    "SECAO INFANTIL",
    # Limpeza — tokens genéricos (bigramas específicos em _VOCAB_CATEGORIA têm prioridade)
    "CERA":         "LIMPEZA DE PISOS",         # CERA LIQUIDA bigrama já cobre o específico
    # Higiene — ESCOVA DENTAL bigrama já cobre o específico; standalone → higiene corporal
    "BUCHA":        "HIGIENE CORPORAL",
    "ESCOVA":       "HIGIENE CORPORAL",
    # Bazar — descartáveis
    "SACOLA":       "UTILIDADES DESCARTAVEIS",
    # BOBINA movido para _VOCAB_CATEGORIA (categoria BOBINAS TERMICAS)
    "PALITO":       "UTILIDADES DESCARTAVEIS",  # palito de dente / churrasco
    # Bebidas
    "DRINK":        "DESTILADOS",               # drink pronto / coquetel
    # Matinais
    "FILTRO":       "MATINAIS",                 # filtro de papel para café
    "ERVA":         "MATINAIS",                 # erva-mate
    # Açougue
    "TORRESMO":     "SUINO",
    # Capilares
    "REPARADOR":    "PRODUTOS CAPILARES",       # reparador de pontas
    # Têxtil
    "TOALHA":       "CAMA, MESA, BANHO",
    # Utensílios de limpeza
    "FLANELA":      "UTENSILIOS PARA LIMPEZA",
    "ESPUMA":       "UTENSILIOS PARA LIMPEZA",  # esponja de espuma
    # Papelaria
    "CADERNO":      "ARTIGOS PARA PAPELARIA E ARMARINHO",
    "TESOURA":      "ARTIGOS PARA PAPELARIA E ARMARINHO",
    # Utilidades da cozinha
    "COLHER":       "UTILIDADES DA COZINHA",
    # Ferramentas e elétricos
    "GRAXA":        "FERRAMENTAS E ACESSORIOS",
    "CADEADO":      "FERRAMENTAS E ACESSORIOS",
    "EXTENSAO":     "FERRAMENTAS E ACESSORIOS",
    "MANGUEIRA":    "FERRAMENTAS E ACESSORIOS",
    # Papelaria
    "CADERNO":      "ARTIGOS PARA PAPELARIA E ARMARINHO",
    # Higiene corporal — HASTE FLEXÍVEL tem acento no banco; usa grupo
    "HASTE FLEXIVEL":  "HIGIENE CORPORAL",
    "HASTES FLEXIVEIS":"HIGIENE CORPORAL",
    # Produtos capilares — GEL é ambíguo mas no contexto supermercado é capilar
    "GEL":          "PRODUTOS CAPILARES",
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
    "ABACATE": "FRUTAS", "KIWI": "FRUTAS", "MEXERICA": "FRUTAS", "TANGERINA": "FRUTAS",
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
    # ESPONJA ACO → vai para UTENSILIOS PARA LIMPEZA (categoria específica), não LIMPEZA DE COZINHA
    "ESPONJA ACO":      ("ESPONJA DE ACO E SINTETICA",   "UTENSILIOS PARA LIMPEZA"),
    "DESENGORDURANTE":  ("DESENGORDURANTES",             None),
    "SAPONACEO":        ("SAPONACEOS PO",                None),
    # ══ LIMPEZA DE CASA ══════════════════════════════════════════════
    # DESINFETANTES ATE 500ML está em LIMPEZA DE BANHEIRO (não LIMPEZA DE CASA)
    "DESINFETANTE":     ("DESINFETANTES ATE 500ML",      "LIMPEZA DE BANHEIRO"),
    "ALCOOL":           ("ALCOOL",                       "LIMPEZA DE CASA"),
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
    "PETIT SUISSE":     ("PETIT SUISSE",                  "LATICINIOS"),  # categoria real no banco
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
    # "COCA COLA"/"PEPSI COLA" precisam de entrada própria como bigrama: sem
    # elas, "REFRIGERANTE COCA COLA ..." não bate "REFRIGERANTE COLA" (COCA
    # separa as palavras) e cai no unigrama "COLA" → COLAS E ADESIVOS (errado).
    "REFRIGERANTE COLA":    ("REFRIGERANTE COLA",        None),
    "COCA COLA":            ("REFRIGERANTE COLA",        None),
    "PEPSI COLA":           ("REFRIGERANTE COLA",        None),
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
    "SUCO PRONTO":      ("SUCO PRONTO / NECTAR",         None),
    "NECTAR":           ("SUCO PRONTO / NECTAR",         None),
    "NÉCTAR":           ("SUCO PRONTO / NECTAR",         None),
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
    "BISCOITO RECHEADO":    ("BISCOITO RECHEADO",            None),
    "BISCOITO MAIZENA":     ("BISCOITO MAIZENA",             None),
    "BISCOITO MARIA":       ("BISCOITO MARIA",               None),
    "BISCOITO AMANTEIGADO": ("BISCOITO AMENTEIGADO",         "BISCOITO DOCE"),  # bridge grafia popular → DB
    "CLUB SOCIAL":          ("AGUA E SAL",                   "BISCOITO SALGADO"),
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
    # ══ COMMODITIES — AÇÚCAR (tipos específicos) ═════════════════════════
    "ACUCAR MASCAVO":   ("ACUCAR MASCAVO",               "ACUCAR"),
    "ACUCAR REFINADO":  ("ACUCAR REFINADO",              "ACUCAR"),
    "ACUCAR CRISTAL":   ("ACUCAR CRISTAL",               "ACUCAR"),
    "ACUCAR DEMERARA":  ("ACUCAR MASCAVO",               "ACUCAR"),   # sem categoria própria, mais próxima
    # ══ MERCEARIA DOCE — CULINÁRIA ═══════════════════════════════════════
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
    "BANANADA":         ("DOCES DE FRUTAS",              "SOBREMESAS E OUTROS DOCES"),
    "GOIABADA":         ("DOCES DE FRUTAS",              "SOBREMESAS E OUTROS DOCES"),
    "DOCE DE FRUTA":    ("DOCES DE FRUTAS",              "SOBREMESAS E OUTROS DOCES"),
    "DOCES DE FRUTAS":  ("DOCES DE FRUTAS",              "SOBREMESAS E OUTROS DOCES"),
    # ══ MERCEARIA DOCE — SALGADINHOS ═════════════════════════════════
    "SALGADINHO":         ("SALGADINHOS SABORES",        None),
    "BATATA PALHA":       ("BATATA PALHA",               None),
    "BATATA FRITA":       ("BATATA FRITA",               None),
    "ELMA CHIPS":         ("BATATA FRITA",               None),
    "BATATA ELMA CHIPS":  ("BATATA FRITA",               None),
    "AMENDOIM":         ("AMENDOIM",                     "SALGADINHO"),
    "PIPOCA":           ("PIPOCA EM GERAL",              None),
    # ══ MERCEARIA DOCE — BISCOITOS (adicional) ═══════════════════════
    "BOLINHO":          ("BOLINHOS",                     "BISCOITO DOCE"),
    # ══ MERCEARIA DOCE — GULOSEIMAS ══════════════════════════════════
    "BALA":             ("BALAS COMUM",                  None),
    "CHICLETE":         ("GOMA DE MASCAR",               None),
    "CHICLE":           ("GOMA DE MASCAR",               None),
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
    "SHOYU":            ("MOLHO DE SOJA",                "TEMPEROS E MOLHOS"),
    "MOLHO INGLES":     ("MOLHO INGLES E OUTROS",        None),
    "CALDO TABLETE":    ("CALDO TABLETE E PO",           None),
    # ══ MERCEARIA SALGADA — MASSAS E SOPAS ══════════════════════════
    "MACARRAO INSTANTANEO": ("MACARRAO INSTANTANEO",     None),
    "SOPAO":                ("SOPAS",                    "MASSAS E SOPAS"),
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
    # FRALDA: "FRALDAS DESCARTÁVEIS PARA BEBÊ" tem char especial no banco (Ê)
    # → movido para _VOCAB_TIPO_PRODUTO (grupo SECAO INFANTIL) para evitar mismatch
    "LENCO UMEDECIDO":  ("LENCOS UMEDECIDOS",            "SECAO INFANTIL"),
    # ══ APERITIVOS ═══════════════════════════════════════════════════
    "APERITIVO":          ("APERITIVOS EM GERAL",      "EMPORIO GRANEL"),
    # ══ PAPELARIA ════════════════════════════════════════════════════
    "APONTADOR":          ("APONTADORES EM GERAL",     "ARTIGOS PARA PAPELARIA E ARMARINHO"),
    "CANETA":             ("CANETAS EM GERAL",         "ARTIGOS PARA PAPELARIA E ARMARINHO"),
    "MARCADOR":           ("CANETAS EM GERAL",         "ARTIGOS PARA PAPELARIA E ARMARINHO"),  # marcador permanente
    # ══ CAPILARES — ESPECÍFICOS ══════════════════════════════════════
    "ATIVADOR DE CACHOS": ("CREME PARA PENTEAR",       "PRODUTOS CAPILARES"),
    # ══ MERCEARIA DOCE — CEREAIS ═════════════════════════════════════
    "AVEIA":              ("CEREAIS",                  "MATINAIS"),
    "MINGAU":             ("CEREAIS",                  "MATINAIS"),
    # ══ CULINÁRIA DOCE — COMPLEMENTOS ════════════════════════════════
    # Bigramas para CORANTE evitar conflito com "CORANTE" de limpeza (_VOCAB_TIPO_PRODUTO)
    # ══ CAPILARES — BIGRAMAS (expansões de abreviações) ═════════════
    # SHAMPOO e CREME PENTEAR já declarados acima — não duplicar
    "CREME TRATAMENTO":    ("CREMES P/ HIDRATACAO",      "PRODUTOS CAPILARES"),  # resultado da expansão CREME TRAT
    "MASCARA CAPILAR":     ("CREMES P/ HIDRATACAO",      "PRODUTOS CAPILARES"),  # resultado da expansão MASC CAP
    "CREME ALISANTE":      ("ALISANTE E RELAXAMENTO",    "PRODUTOS CAPILARES"),
    # ══ HIGIENE BUCAL ═════════════════════════════════════════════════
    # ANTISSÉPTICO BUCAL tem acento no banco → match via _VOCAB_TIPO_PRODUTO → grupo HIGIENE BUCAL
    # "ENXAGUANTE" fica apenas em _VOCAB_TIPO_PRODUTO (sem duplicata aqui)
    # ══ HIDRATANTES ═══════════════════════════════════════════════════
    "HIDRATANTE":          ("HIDRATANTES CORPORAL",      "CREMES HIDRATANTES"),
    # ══ BAZAR — FERRAMENTAS E ELÉTRICOS ══════════════════════════════
    "PILHA":               ("PILHAS E BATERIAS",         "FERRAMENTAS E ACESSORIOS"),
    # LÂMPADAS tem acento no banco → match via _VOCAB_TIPO_PRODUTO → grupo FERRAMENTAS E ACESSORIOS
    # ══ LIMPEZA — BANHEIRO ════════════════════════════════════════════
    "PEDRA SANIT":         ("DESODORIZADOR SANITARIO",   "LIMPEZA DE BANHEIRO"),
    # ══ MERCEARIA SALGADA ─ TEMPEROS ═════════════════════════════════
    "CUP NOODLES":         ("MACARRAO INSTANTANEO",      "MASSAS E SOPAS"),
    "CEREAL MATINAL":      ("CEREAIS",                   "MATINAIS"),
    "COLORIFICO":          ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS"),
    # ══ CULINÁRIA DOCE — COMPLEMENTOS ════════════════════════════════
    "CORANTE ALIMENTICIO": ("COMPLEMENTOS",            "CULINARIA DOCE"),
    "CORANTE ALIMENTAR":   ("COMPLEMENTOS",            "CULINARIA DOCE"),
    "ANILINA":             ("COMPLEMENTOS",            "CULINARIA DOCE"),
    "ESSENCIA":            ("COMPLEMENTOS",            "CULINARIA DOCE"),
    # ══ PERFUMARIA — FARMÁCIA ═════════════════════════════════════════
    "AGUA OXIGENADA":      ("OUTROS FARMACOS",         "FARMACIA"),
    "PRESERVATIVO":        ("PRESERVATIVOS",           "FARMACIA"),
    # ══ PERECÍVEIS — FRIAMBRERIA ══════════════════════════════════════
    "BANHA":               ("BANHAS E GORDUDAS VEGETAIS", "FRIAMBRERIA"),  # typo proposital: nome exato do banco
    "BACON":               ("DEFUMADOS DA FRIAMBRERIA", "FRIAMBRERIA"),
    # ══ PADARIA ═══════════════════════════════════════════════════════
    "PAO DE FORMA":        ("PAO DE FORMA COMUM",       "PADARIA INDUSTRIAL"),
    # ══ BAZAR — UTILIDADES DA COZINHA ════════════════════════════════
    "SACA ROLHA":          ("OUTRAS UTILIDADES DE COZINHA", "UTILIDADES DA COZINHA"),
    # ══ USO E CONSUMO — EMBALAGENS ═══════════════════════════════════
    "BOBINA":              ("BOBINAS TERMICAS",             "EMBALAGENS E BOBINAS TERMICAS"),
    # ══ BAZAR — MATERIAL ELÉTRICO ════════════════════════════════════
    "BENJAMIN":            ("MATERIAL ELETRICO",            "FERRAMENTAS E ACESSORIOS"),
    # ══ BARBEARIA ════════════════════════════════════════════════════
    "APARELHO DE BARBEAR": ("APARELHOS DESCARTÁVEIS",    "BARBEARIA"),
    "APARELHO BARBEAR":    ("APARELHOS DESCARTÁVEIS",    "BARBEARIA"),
    "LAMINA":              ("LAMINAS (REFIL)",            "BARBEARIA"),   # standalone
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
    # ══ FERRAMENTAS — COLAS E ADESIVOS ═══════════════════════════════
    # COLA BRANCA vai para papelaria. NÃO cadastrar "COLA" sozinho: é ambíguo
    # com "COCA COLA"/"PEPSI COLA"/outras marcas de refrigerante ("PLANETA
    # COLA", "TROPICAL COLA") — um unigrama aqui tem prioridade sobre o
    # REFRIGERANTE do vocab de tipo_produto (checado depois) e classificava
    # bebida como cola de colar com 0.98 de confiança. Cola de colar genérica
    # (Loctite, Super Bonder etc.) sem marca reconhecida cai em revisão manual.
    "COLA BRANCA":      ("COLAS E FITA ADESIVA",         "ARTIGOS PARA PAPELARIA E ARMARINHO"),
    "COLA MASSA":       ("COLAS E ADESIVOS",             "FERRAMENTAS E ACESSORIOS"),
    # ══ AÇOUGUE ══════════════════════════════════════════════════════
    "LINGUICA":         ("LINGUICA GRANEL ATENDIMENTO",  None),
    "SALSICHA":         ("SALSICHA GRANEL ATENDIMENTO",  None),
    # ══ NUTRIÇÃO INFANTIL ════════════════════════════════════════════
    "PAPINHA":          ("PAPINHAS",                     None),
    # ══ MERCEARIA SALGADA — BISCOITO SALGADO ════════════════════════
    "SALPET":             ("SALPET",                     "BISCOITO SALGADO"),
    # ══ TEMPEROS ESPECÍFICOS ══════════════════════════════════════════
    "COMINHO":            ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS"),
    "PIMENTA":            ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS"),  # pimenta do reino / calabresa
    "PAPRICA":            ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS"),
    # ══ MERCEARIA DOCE — GULOSEIMAS ══════════════════════════════════
    "PACOCA":             ("DOCES DE AMENDOIM",          "GULOSEIMAS"),
    "PACOQUINHA":         ("DOCES DE AMENDOIM",          "GULOSEIMAS"),
    "PACOQUITA":          ("DOCES DE AMENDOIM",          "GULOSEIMAS"),
    # ══ UTILIDADES DA COZINHA — BAZAR ════════════════════════════════
    "PENEIRA":            ("ESCORREDORES E PENEIRAS",    "UTILIDADES DA COZINHA"),
    # ══ TABACARIA ════════════════════════════════════════════════════
    "CIGARRO":          ("CIGARRO EM GERAL",             None),
    # ══ PET SHOP ═════════════════════════════════════════════════════
    "RACAO":            ("ALIMENTO PARA CAES",           "RACAO E PET SHOP"),
    # ══ CARVÃO / CHURRASCO ═══════════════════════════════════════════
    "CARVAO":           ("CARVAO",                       None),
    # ══ PADARIA ══════════════════════════════════════════════════════
    "PAO FRANCES":      ("PAO FRANCES",                  None),
    # PAO DE FORMA já declarado acima com grupo_pref="PADARIA INDUSTRIAL" — não duplicar
    # ══ BEBIDAS — VINHO (complementar) ═══════════════════════════════
    "VINHO ROSE":       ("VINHO ROSE",                   None),
    # ══ TÊXTIL — CALÇADOS ════════════════════════════════════════════
    "SANDALIA HAVAIANA":("SANDALIA E CHINELO",           "CALCADOS"),
    "SANDALIA":         ("SANDALIA E CHINELO",           "CALCADOS"),
    "CHINELO":          ("SANDALIA E CHINELO",           "CALCADOS"),
    "HAVAIANA":         ("SANDALIA E CHINELO",           "CALCADOS"),
    # ══ UTILIDADES DESCARTÁVEIS — VELAS ══════════════════════════════
    "VELA":             ("VELAS COMUM / CITRONELA / AROMÁTICAS", None),
    "VELAS":            ("VELAS COMUM / CITRONELA / AROMÁTICAS", None),
    # ══ UTENSÍLIOS DA COZINHA ════════════════════════════════════════
    "COPO":             ("COPO INDIVIDUAL",              "UTILIDADES DA COZINHA"),
    # ══ CAMA MESA BANHO ══════════════════════════════════════════════
    "TAPETE":           ("TAPETES EM GERAL",             "CAMA, MESA, BANHO"),
    # ══ MERCEARIA DOCE LIGHT E DIET ══════════════════════════════════
    "ADOCANTE":         ("ADOCANTES",                   "MERCEARIA DOCE LIGHT E DIET"),
    # ══ BEBIDAS — DESTILADOS ═════════════════════════════════════════
    "CONHAQUE":         ("CONHAQUE/BRANDY",              "DESTILADOS"),
    # ══ PADARIA INDUSTRIAL ═══════════════════════════════════════════
    "TORRADA":          ("TORRADAS",                    "PADARIA INDUSTRIAL"),
    "TORRADAS":         ("TORRADAS",                    "PADARIA INDUSTRIAL"),
    # ══ LIMPEZA PARA ROUPAS — CLORO ══════════════════════════════════
    "CLORO":            ("ALVEJANTES E CLORO",           "LIMPEZA PARA ROUPAS"),
    # ══ ESTÉTICA — ACETONA ════════════════════════════════════════════
    "ACETONA":          ("REMOVEDORES DE ESMALTES / ACETONA", "ESTETICA"),
    # ══ TEMPEROS ESPECÍFICOS ══════════════════════════════════════════
    "CANELA":           ("TEMPEROS PRONTO EM PO/SACHE", "TEMPEROS E MOLHOS"),
    "OREGANO":          ("TEMPEROS PRONTO EM PO/SACHE", "TEMPEROS E MOLHOS"),
    # ══ LIMPEZA DE BANHEIRO — LIMPEZA PESADA ══════════════════════════
    "SODA CAUSTICA":    ("LIMPEZA PESADA",              "LIMPEZA DE BANHEIRO"),
    # ══ HIGIENE CORPORAL — BUCHA DE BANHO ════════════════════════════
    "BUCHA BANHO":      ("ESPONJA DE BANHO",            "HIGIENE CORPORAL"),
    # ══ CAPILARES — GEL ══════════════════════════════════════════════
    "GEL FIXADOR":      ("GEL FIXADOR",                 "PRODUTOS CAPILARES"),
    "GEL CAPILAR":      ("GEL FIXADOR",                 "PRODUTOS CAPILARES"),
}

# Combinações de palavras NÃO adjacentes que definem uma categoria.
# Usado para resolver ambiguidades onde o produto específico traz dois tokens
# que podem estar separados por marca/nome, ex: "COCO ANCHIETA RALADO".
# Verificado APÓS _VOCAB_CATEGORIA (bigramas adjacentes) e ANTES de _VOCAB_HORTIFRUTI.
# Chave: frozenset de tokens que TODOS devem estar presentes na descrição.
# Valor: (nome_categoria, grupo_preferido|None)
_VOCAB_COMBINACAO: dict[frozenset, tuple[str, str | None, str]] = {
    # Tupla: (nome_para_match, grupo_preferido|None, nivel)
    # nivel = "cat" → chama _match_por_categoria_nome
    # nivel = "grp" → chama _match_por_grupo_nome (quando só existe grupo, sem categoria)

    # ── Tipo 1: token hortifruti + modificador → produto industrializado ──────
    # Fruta seca / desidratada
    frozenset({"BANANA", "PASSA"}):        ("UVA PASSA",                   "FRUTAS SECAS",         "cat"),  # banana passa cai em frutas secas
    frozenset({"COCO", "RALADO"}):         ("COCO RALADO",                 None,                   "cat"),  # COCO ANCHIETA RALADO
    # Temperos desidratados — token hortifruti ganharia LEGUMES sem combinação
    frozenset({"ALHO", "PO"}):             ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # ALHO PO KITANO
    frozenset({"ALHO", "GRANULADO"}):      ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # ALHO GRANULADO
    frozenset({"ALHO", "DESIDRATADO"}):    ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # ALHO DESIDRATADO
    frozenset({"CEBOLA", "FLOCOS"}):       ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # CEBOLA YOKI FLOCOS
    frozenset({"CEBOLA", "DESIDRATADA"}):  ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # CEBOLA DESIDRATADA
    frozenset({"CEBOLA", "PO"}):           ("CALDO TABLETE E PO",          "TEMPEROS E MOLHOS",    "cat"),  # CEBOLA PO
    frozenset({"TOMATE", "SECO"}):         ("OUTRAS CONSERVAS",            "CONSERVAS E ENLATADOS","cat"),
    # Salgadinho de batata — token BATATA ganharia LEGUMES sem combinação
    frozenset({"BATATA", "CHIPS"}):        ("BATATA FRITA",                "SALGADINHO",           "cat"),
    frozenset({"BATATA", "SNACK"}):        ("SALGADINHOS SABORES",         "SALGADINHO",           "cat"),

    # ── Tipo 2: marca quebra bigrama adjacente já correto no _VOCAB_CATEGORIA ─
    # (evita que o token base ganhe a categoria genérica do grupo)
    frozenset({"LEITE", "COCO"}):          ("LEITE DE COCO",               "CULINARIA DOCE",       "cat"),  # LEITE SOCOCO COCO 200ML
    frozenset({"OLEO", "COCO"}):           ("OLEO DE COCO",                "OLEO",                 "cat"),  # OLEO COPRA COCO 500ML
    frozenset({"FARINHA", "MANDIOCA"}):    ("FARINHA DE MANDIOCA",         "FARINACEOS",           "cat"),  # FARINHA YOKI MANDIOCA 1KG
    frozenset({"FARINHA", "TRIGO"}):       ("FARINHA DE TRIGO",            None,                   "grp"),  # FARINHA DONA BENTA TRIGO 1KG — grupo, não categoria

    # ── Tipo 3: subtipo de açúcar separado pela marca ─────────────────────────
    # "ACUCAR NATIVE MASCAVO 1KG" — NATIVE separa os tokens, bigrama adjacente não funciona
    frozenset({"ACUCAR", "MASCAVO"}):      ("ACUCAR MASCAVO",              "ACUCAR",               "cat"),
    frozenset({"ACUCAR", "REFINADO"}):     ("ACUCAR REFINADO",             "ACUCAR",               "cat"),
    frozenset({"ACUCAR", "CRISTAL"}):      ("ACUCAR CRISTAL",              "ACUCAR",               "cat"),
    frozenset({"ACUCAR", "DEMERARA"}):     ("ACUCAR MASCAVO",              "ACUCAR",               "cat"),  # sem categoria própria

    # ── Tipo 4: combinações que identificam subcategoria específica ───────────
    frozenset({"PESSEGO", "CALDA"}):       ("COMPOTAS DE FRUTAS",          "SOBREMESAS E OUTROS DOCES", "cat"),  # PESSEGO CALDA FORNO DE MINAS
    frozenset({"PO", "DESCOLORANTE"}):     ("TINTURA / DESCOLORANTES PARA CABELO", "PRODUTOS CAPILARES", "cat"),  # PO DESCOLORANTE WELLA

    # ── Tipo 5: fruta seca/desidratada ────────────────────────────────────────
    frozenset({"AMEIXA", "SECA"}):         ("FRUTAS SECAS / CRISTALIZADAS","FRUTAS SECAS",             "cat"),  # AMEIXA SECA SUNSWEET

    # ── Tipo 6: biscoitos — token de subtipo separado pela marca ─────────────
    frozenset({"SEQUILHO", "LEITE"}):      ("ROSQUINHAS E SEQUILHOS",      "BISCOITO DOCE",            "cat"),  # SEQUILHO BELLA LEITE 400G
    frozenset({"BISCOITO", "AGUA"}):       ("AGUA E SAL",                  "BISCOITO SALGADO",         "cat"),  # BISCOITO X AGUA E SAL
    frozenset({"BISCOITO", "MAIZENA"}):    ("BISCOITO MAIZENA",            "BISCOITO DOCE",            "cat"),  # BISCOITO BAUDUCCO MAIZENA
    frozenset({"BISCOITO", "RECHEADO"}):   ("BISCOITO RECHEADO",           "BISCOITO DOCE",            "cat"),  # BISCOITO TRAKINAS RECHEADO
    frozenset({"BISCOITO", "CRACKER"}):    ("CREAM CRACKER",               "BISCOITO SALGADO",         "cat"),  # BISCOITO X CRACKER
    frozenset({"BISCOITO", "AMANTEIGADO"}):("BISCOITO AMENTEIGADO",        "BISCOITO DOCE",            "cat"),  # BISCOITO X AMANTEIGADO

    # ── Tipo 7: outros ────────────────────────────────────────────────────────
    frozenset({"BANANA", "CHIPS"}):        ("SNACKS",                      "SALGADINHO",               "cat"),  # BANANA CHIPS NATURAL
    frozenset({"BARRA", "CEREAL"}):        ("CEREAIS EM BARRA",            "MERCEARIA DOCE LIGHT E DIET","cat"), # BARRA NUTRY CEREAL
    frozenset({"BICARBONATO", "SODIO"}):   ("TEMPEROS PRONTO EM PO/SACHE", "TEMPEROS E MOLHOS",        "cat"),  # BICARBONATO SODIO ARM & HAMMER

    # ── Tipo 8: banha/gordura suína ───────────────────────────────────────────
    frozenset({"BANHA", "SUINA"}):         ("BANHAS E GORDUDAS VEGETAIS",  "FRIAMBRERIA",              "cat"),  # BANHA AURORA SUINA 500G
    frozenset({"GORDURA", "SUINA"}):       ("BANHAS E GORDUDAS VEGETAIS",  "FRIAMBRERIA",              "cat"),  # GORDURA SUINA SADIA 500G

    # ── Tipo 9: limpeza e utilidades ──────────────────────────────────────────
    frozenset({"SABAO", "COCO"}):          ("SABAO EM BARRA E PASTA",      "LIMPEZA PARA ROUPAS",      "cat"),  # SABAO BARRA COCO BRILHANTE
    frozenset({"BALDE", "PLASTICO"}):      ("BALDES DE PLASTICO",          "UTILIDADES DA COZINHA",    "cat"),  # BALDE PLASTICO 10L

    # ── Tipo 10: padaria e frios ──────────────────────────────────────────────
    frozenset({"PAO", "BATATA"}):          ("PAES ESPECIAIS",              "PANIFICACAO PRODUCAO PROPRIA", "cat"),  # PAO DE BATATA / PAO BATATA RECHEADO
    frozenset({"BACON", "CUBOS"}):         ("DEFUMADOS DA FRIAMBRERIA",    "FRIAMBRERIA",              "cat"),  # BACON AURORA CUBOS 100G
    frozenset({"BACON", "DEFUMADO"}):      ("DEFUMADOS DA FRIAMBRERIA",    "FRIAMBRERIA",              "cat"),  # BACON DEFUMADO SADIA
    # ── Tipo 16: congelados — proteína congelada vs fresca/atendimento ───────
    frozenset({"LINGUICA", "CONGELADA"}):  ("LINGUICA CONGELADA",          "CONGELADOS",               "cat"),  # LINGUICA AURORA CONGELADA 500G
    frozenset({"LINGUICA", "CONGELADO"}):  ("LINGUICA CONGELADA",          "CONGELADOS",               "cat"),  # LINGUICA FRIGORIFICA CONGELADO

    # ── Tipo 11: temperos — pimenta separada pela marca ───────────────────────
    frozenset({"PIMENTA", "REINO"}):       ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",         "cat"),  # PIMENTA DO REINO INCOREG 10G
    frozenset({"PIMENTA", "CALABRESA"}):   ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",         "cat"),  # PIMENTA CALABRESA INCOREG 8G
    frozenset({"PIMENTA", "MALAGUETA"}):   ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",         "cat"),  # PIMENTA MALAGUETA INCOREG
    frozenset({"PIMENTA", "COMINHO"}):     ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",         "cat"),  # PIMENTA C/ COMINHO INCOREG

    # ── Tipo 12: lixo e limpeza ───────────────────────────────────────────────
    frozenset({"LIXO", "SACO"}):           ("SACOS PARA LIXO",            "UTENSILIOS PARA LIMPEZA",   "cat"),  # LIXO FIX LIXO ALMOFADA SACO 15L
    frozenset({"LIMPADOR", "PERFUME"}):    ("MULTIUSO",                   "LIMPEZA DE CASA",            "cat"),  # LIMPADOR PERFUMADO UAU / AGRADABLE

    # ── Tipo 13: capilares — marca separa tokens ──────────────────────────────
    frozenset({"CREME", "TRATAMENTO"}):   ("CREMES P/ HIDRATACAO",        "PRODUTOS CAPILARES",         "cat"),  # CREME ELSEVE TRATAMENTO 450G
    # ── Tipo 14: desodorante por subtipo ─────────────────────────────────────
    frozenset({"DESODORANTE", "AEROSOL"}):("DESODORANTE AEROSOL",         "DESODORANTES E COLONIAS",    "cat"),  # DES REXONA AEROSOL 150ML
    frozenset({"DESODORANTE", "SPRAY"}):  ("DESODORANTE AEROSOL",         "DESODORANTES E COLONIAS",    "cat"),  # DES DOVE SPRAY 150ML
    # ── Tipo 15: sementes alimentícias — SEMENTE + nome define produto industrial
    frozenset({"SEMENTE", "GIRASSOL"}):   ("SEMENTES (CHIA, LINHACA, GIRASSOL, ETC.)", "FARINACEOS",   "cat"),  # SEMENTE DE GIRASSOL YOKI 100G
    frozenset({"SEMENTE", "CHIA"}):       ("SEMENTES (CHIA, LINHACA, GIRASSOL, ETC.)", "FARINACEOS",   "cat"),  # SEMENTE CHIA YOKI
    frozenset({"SEMENTE", "LINHACA"}):    ("SEMENTES (CHIA, LINHACA, GIRASSOL, ETC.)", "FARINACEOS",   "cat"),  # SEMENTE LINHACA DOURADA
    frozenset({"SEMENTE", "GERGELIM"}):   ("SEMENTES (CHIA, LINHACA, GIRASSOL, ETC.)", "FARINACEOS",   "cat"),  # SEMENTE GERGELIM

    # ── Tipo 17: peixe + modificador define fresco vs congelado ──────────────
    frozenset({"PEIXE", "POSTAS"}):       ("PEIXES CONGELADO",         "CONGELADOS",            "cat"),  # PEIXE MERLUZA POSTAS 800G
    frozenset({"PEIXE", "POSTA"}):        ("PEIXES CONGELADO",         "CONGELADOS",            "cat"),  # PEIXE TILAPIA POSTA 1KG
    frozenset({"PEIXE", "FILE"}):         ("PEIXES CONGELADO",         "CONGELADOS",            "cat"),  # PEIXE FILE TILAPIA 400G
    frozenset({"PEIXE", "INTEIRO"}):      ("PEIXE FRESCO",             "PEIXES",                "cat"),  # PEIXE INTEIRO KG (açougue)

    # ── Tipo 18: cacau em pó → culinária doce (não chocolates de barra) ──────
    frozenset({"CACAU", "PO"}):           ("CHOCOLATES EM PO",         "CULINARIA DOCE",        "cat"),  # CACAU PO GAROTO 200G

    # ── Tipo 19: azeite — marca separa AZEITE ... VIRGEM ─────────────────────
    frozenset({"AZEITE", "VIRGEM"}):      ("AZEITE EXTRA VIRGEM",      "AZEITES",               "cat"),  # AZEITE GALLO EXTRA VIRGEM 500ML

    # ── Tipo 20: vinagres com modificador separado por marca ──────────────────
    frozenset({"VINAGRE", "MACA"}):       ("VINAGRE DE MACA",          "VINAGRES",              "cat"),  # VINAGRE MACA HEINZ 500ML
    frozenset({"VINAGRE", "ARROZ"}):      ("VINAGRE DE ARROZ",         "VINAGRES",              "cat"),  # VINAGRE ARROZ SUSHI

    # ── Tipo 21: chocolate em barra — marca separa CHOCOLATE ... BARRA ───────
    frozenset({"CHOCOLATE", "BARRA"}):    ("CHOCOLATE EM BARRAS",      "CHOCOLATES",            "cat"),  # CHOCOLATE LACTA BARRA 170G

    # ── Tipo 22: noz moscada — NOZ sozinho iria para FRUTAS SECAS ────────────
    frozenset({"NOZ", "MOSCADA"}):        ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",   "cat"),  # NOZ MOSCADA INCOREG 15G

    # ── Tipo 23: cervejas — marca/volume separa subtipo ──────────────────────
    frozenset({"CERVEJA", "LATA"}):       ("CERVEJA LATA",             "CERVEJAS",              "cat"),  # CERVEJA SKOL LATA 350ML
    frozenset({"CERVEJA", "LATAO"}):      ("CERVEJA LATA",             "CERVEJAS",              "cat"),  # CERVEJA BRAHMA LATAO 473ML
    frozenset({"CERVEJA", "LONG"}):       ("CERVEJA LONG NECK",        "CERVEJAS",              "cat"),  # CERVEJA HEINEKEN LONG NECK
    frozenset({"CERVEJA", "NECK"}):       ("CERVEJA LONG NECK",        "CERVEJAS",              "cat"),  # CERVEJA CORONA LONG NECK 330ML

    # ── Tipo 24: massas — tipo separado por marca ─────────────────────────────
    frozenset({"MACARRAO", "SEMOLA"}):    ("MASSA SEMOLA",             "MASSAS E SOPAS",        "cat"),  # MACARRAO BARILLA SEMOLA 500G
    frozenset({"MACARRAO", "OVOS"}):      ("MASSA COM OVOS",           "MASSAS E SOPAS",        "cat"),  # MACARRAO RENATA OVOS 500G
    frozenset({"MASSA", "PASTEL"}):       ("OUTRAS MASSAS",            "MASSAS E SOPAS",        "cat"),  # MASSA AROSA PASTEL 500G

    # ── Tipo 25: sopas — creme de cebola / tempero de sopa ───────────────────
    frozenset({"CREME", "CEBOLA"}):       ("SOPAS",                    "MASSAS E SOPAS",        "cat"),  # CREME CEBOLA KNORR 60G

    # ── Tipo 26: caldos de marca (token CALDO + marca específica) ────────────
    frozenset({"CALDO", "KNORR"}):        ("CALDO TABLETE E PO",       "TEMPEROS E MOLHOS",     "cat"),  # CALDO KNORR GALINHA 57G
    frozenset({"CALDO", "MAGGI"}):        ("CALDO TABLETE E PO",       "TEMPEROS E MOLHOS",     "cat"),  # CALDO MAGGI CARNE 37G

    # ── Tipo 27: molhos — marca separa MOLHO do tipo ─────────────────────────
    frozenset({"MOLHO", "TOMATE"}):       ("MOLHOS E POLPAS TOMATE",   "TEMPEROS E MOLHOS",     "cat"),  # MOLHO AURORA TOMATE 340G
    frozenset({"MOLHO", "PIMENTA"}):      ("MOLHO DE PIMENTA",         "TEMPEROS E MOLHOS",     "cat"),  # MOLHO TABASCO PIMENTA 60ML

    # ── Tipo 28: laticínios — marca separa tokens ─────────────────────────────
    frozenset({"CREME", "LEITE"}):        ("CREME DE LEITE",           "CULINARIA DOCE",        "cat"),  # CREME NESTLÉ LEITE 200G
    frozenset({"DOCE", "LEITE"}):         ("DOCES DE LEITE",           "SOBREMESAS E OUTROS DOCES", "cat"),  # DOCE VIGOR LEITE 400G

    # ── Tipo 29: temperos com marca ───────────────────────────────────────────
    frozenset({"TEMPERO", "SAZON"}):      ("TEMPEROS PRONTO EM PO/SACHE","TEMPEROS E MOLHOS",   "cat"),  # TEMPERO SAZON FRANGO 60G

    # ── Tipo 30: leite em pó — marca separa LEITE e PO ───────────────────────
    frozenset({"LEITE", "PO"}):           ("LEITE EM PO",              "LEITE",                 "cat"),  # LEITE NINHO PO 400G

    # ── Tipo 31: capilares — reparador de pontas ──────────────────────────────
    frozenset({"REPARADOR", "PONTAS"}):   ("PRODUTOS CAPILARES",       None,                    "grp"),  # REPARADOR ELVIVE PONTAS 200ML

    # ── Tipo 32: feijão — subtipo separado por marca ──────────────────────────
    frozenset({"FEIJAO", "CARIOCA"}):     ("FEIJAO CARIOCA",           "FEIJAO",                "cat"),  # FEIJAO CAMIL CARIOCA 1KG
    frozenset({"FEIJAO", "PRETO"}):       ("FEIJAO PRETO",             "FEIJAO",                "cat"),  # FEIJAO CAMIL PRETO 1KG
    frozenset({"FEIJAO", "BRANCO"}):      ("FEIJAO BRANCO",            "FEIJAO",                "cat"),  # FEIJAO BRANCO 1KG
    frozenset({"FEIJAO", "CORDA"}):       ("FEIJAO DE CORDA",          "FEIJAO",                "cat"),  # FEIJAO DE CORDA 1KG
    frozenset({"FEIJAO", "JALO"}):        ("FEIJAO JALO",              "FEIJAO",                "cat"),  # FEIJAO JALO 1KG

    # ── Tipo 33: utensílios — abridor separado do objeto ──────────────────────
    frozenset({"ABRIDOR", "LATA"}):       ("OUTRAS UTILIDADES DE COZINHA", "UTILIDADES DA COZINHA", "cat"),
    frozenset({"ABRIDOR", "LATAS"}):      ("OUTRAS UTILIDADES DE COZINHA", "UTILIDADES DA COZINHA", "cat"),
    frozenset({"ABRIDOR", "VINHO"}):      ("OUTRAS UTILIDADES DE COZINHA", "UTILIDADES DA COZINHA", "cat"),  # saca-rolha
    frozenset({"AFIADOR", "FACA"}):       ("OUTRAS UTILIDADES DE COZINHA", "UTILIDADES DA COZINHA", "cat"),

    # ── Tipo 34: absorvente com abas ──────────────────────────────────────────
    frozenset({"ABSORVENTE", "ABAS"}):    ("ABSORVENTE EXTERNO",       "ABSORVENTES",           "cat"),

    # ── Tipo 35: estética — manicure ──────────────────────────────────────────
    frozenset({"ALICATE", "CUTICULA"}):   ("ACESSORIOS MANICURE",      "ESTETICA",              "cat"),
    frozenset({"CORTADOR", "UNHAS"}):     ("ACESSORIOS MANICURE",      "ESTETICA",              "cat"),

    # ── Tipo 36: água de coco — marca separa AGUA e COCO ─────────────────────
    frozenset({"AGUA", "COCO"}):          ("AGUA DE COCO",             "AGUAS",                 "cat"),  # AGUA SOCOCO COCO 1L

    # ── Tipo 37: café solúvel — marca separa CAFE e SOLUVEL ───────────────────
    frozenset({"CAFE", "SOLUVEL"}):       ("CAFE SOLUVEL",             "MATINAIS",              "cat"),  # CAFE NESCAFE SOLUVEL 200G

    # ── Tipo 38: desodorante por subtipo (marca separa DESODORANTE do tipo) ───
    frozenset({"DESODORANTE", "ROLLON"}): ("DESODORANTE ROLLON",       "DESODORANTES E COLONIAS","cat"),  # DESODORANTE DOVE ROLLON 50ML
    frozenset({"DESODORANTE", "CREME"}):  ("DESODORANTE CREME",        "DESODORANTES E COLONIAS","cat"),  # DESODORANTE REXONA CREME 58G

    # ── Tipo 39: óleo capilar — OLEO sozinho iria para óleo alimentício ───────
    frozenset({"OLEO", "CAPILAR"}):       ("CREMES P/ HIDRATACAO",     "PRODUTOS CAPILARES",    "cat"),  # OLEO CAPILAR ELSEVE 100ML

    # ── Tipo 40: sal grosso — SAL sozinho vai para o grupo genérico ───────────
    frozenset({"SAL", "GROSSO"}):         ("SAL GROSSO",               "SAL",                   "cat"),  # SAL GROSSO LEBRE 1KG
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

    # 0a. Combinações não adjacentes (prioridade alta: resolve antes dos vocabs de grupo).
    #     Cobre casos como "COCO ANCHIETA RALADO" e "FARINHA YOKI MANDIOCA 1KG"
    #     onde a marca separa os tokens que definem a categoria.
    tokens_set = set(palavras)
    for combinacao, (cat_nome, grp_pref, nivel) in _VOCAB_COMBINACAO.items():
        if combinacao.issubset(tokens_set):
            if nivel == "grp":
                return _match_por_grupo_nome(cat_nome, session, score=0.97)
            return _match_por_categoria_nome(cat_nome, session, score=0.97,
                                             grupo_preferido=grp_pref)

    # 0b. Vocabulário de tipo de produto (evita conflitos como MACA → FRUTAS em VINAGRE DE MACA)
    #     Bigramas primeiro (ex: "FARINHA DE TRIGO" > "FARINHA")
    for i in range(len(palavras) - 1):
        bigrama = f"{palavras[i]} {palavras[i+1]}"
        if bigrama in _VOCAB_TIPO_PRODUTO:
            return _match_por_grupo_nome(_VOCAB_TIPO_PRODUTO[bigrama], session, score=0.95)
    for token in palavras:
        if token in _VOCAB_TIPO_PRODUTO:
            return _match_por_grupo_nome(_VOCAB_TIPO_PRODUTO[token], session, score=0.95)

    # normalizado igual tokens_item (minúsculo, sem acento) — senão a comparação
    # de _melhor_match nunca bate (palavras[0] é maiúsculo, tokens_item minúsculo)
    _lista_normalizada = _normalizar_lista(descricao)
    primeira_palavra = _lista_normalizada[0] if _lista_normalizada else None

    # 1. Tenta match em categorias (mais específico)
    melhor_cat = _melhor_match(tokens_desc, _INDICE_CATEGORIAS, primeira_palavra)
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
    melhor_grp = _melhor_match(tokens_desc, _INDICE_GRUPOS, primeira_palavra)
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

    # 3. Último recurso: vocabulário de hortifruti (bigramas primeiro: BATATA DOCE > BATATA)
    #    Roda por último de propósito — nome de fruta/legume sozinho é sinal fraco
    #    ("CREME SKALA MORANGO", "XAROPE UVA", "HAV KIDS FLORES" não são hortifruti).
    #    Fica atrás do fallback fuzzy pra dar chance a um match mais específico
    #    (que já tem proteção anti-token-ambíguo em _melhor_match) antes de assumir
    #    que é fruta/legume de verdade.
    #    Só aceita se a fruta/legume for a PRIMEIRA palavra: descrição de hortifruti
    #    real começa pelo produto ("LARANJA KG", "BATATA KG"); nos falsos positivos
    #    a fruta aparece no meio/fim como sabor/aroma de outro produto ("CREME
    #    SKALA MORANGO", "TIC TAC SABORES MORANGO", "XAROPE MORANGO CERESER").
    if len(palavras) >= 2 and f"{palavras[0]} {palavras[1]}" in _VOCAB_HORTIFRUTI:
        return _match_por_grupo_nome(_VOCAB_HORTIFRUTI[f"{palavras[0]} {palavras[1]}"], session, score=0.90)
    if palavras and palavras[0] in _VOCAB_HORTIFRUTI:
        return _match_por_grupo_nome(_VOCAB_HORTIFRUTI[palavras[0]], session, score=0.90)

    return _vazio()


# ── Helpers ───────────────────────────────────────────────────────────────────

# Conectores sem valor semântico — não contam como token "em comum" no fuzzy match
_CONECTORES: set[str] = {
    "de", "da", "do", "das", "dos", "e", "em", "com", "sem", "para",
    "por", "ao", "a", "o", "as", "os", "no", "na", "nos", "nas",
}

def _melhor_match(
    tokens_desc: set[str], indice: list[dict], primeira_palavra: str | None = None
) -> dict | None:
    """
    Retorna o item do índice com maior score de cobertura.

    Score = intersecao / len(tokens_item)
    Regra anti-falso-positivo: para itens com 2+ tokens, exige intersecao >= 2.
    Isso evita que um único token ambíguo ("BARRA", "ROSA", "CRISTAL")
    cause um match errado com categorias como "SABONETE EM BARRA" ou "SAL ROSA".

    Itens de 1 token só (ex: grupo "FLORES", "SAL", "OLEO") não têm essa proteção
    — qualquer ocorrência do token em QUALQUER lugar da descrição dá score 1.0,
    então "HAV KIDS FLORES BEGE" (chinelo estampa floral) batia grupo FLORES
    (hortifruti) igual a "ROSAS VERMELHAS BUQUE". Pra esses, exige que o token
    seja a primeira palavra da descrição — hortifruti/commodity de verdade
    começa pelo produto ("SAL GROSSO 1KG"), não tem ele no meio como
    ingrediente/aroma de outra coisa ("SAL DE FRUTAS ENO").
    """
    melhor = None
    melhor_score = 0.0
    for item in indice:
        tokens_item = item["tokens"]
        if not tokens_item:
            continue
        # Conectores ("DE", "COM"...) não contam pra interseção — senão "ROSCA DE
        # COCO" (pão) bate "AGUA DE COCO" só porque "DE"+"COCO" somam 2 tokens em
        # comum, satisfazendo a regra abaixo sem nenhuma relação real de sentido.
        intersecao_tokens = (tokens_desc & tokens_item) - _CONECTORES
        intersecao = len(intersecao_tokens)
        if intersecao == 0:
            continue
        # Anti falso-positivo: itens multi-token exigem ao menos 2 matches
        if len(tokens_item) >= 2 and intersecao < 2:
            continue
        # Anti falso-positivo: item de 1 token só precisa ser a primeira palavra
        if len(tokens_item) == 1 and primeira_palavra not in tokens_item:
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
