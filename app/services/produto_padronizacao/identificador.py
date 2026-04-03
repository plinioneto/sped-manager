# Dicionário de marcas conhecidas.
# Estrutura: nome_canônico_da_marca → {fabricante, aliases, categoria}
# - fabricante: nome do grupo empresarial / fabricante real
# - aliases: variações de escrita encontradas em descrições de supermercado
# - categoria: classificação ampla do produto (para contexto)
#
# Regra de negócio:
#   - marca = a marca comercial visível no produto (DOVE, SADIA, SKOL...)
#   - fabricante = quem produz / o grupo empresarial (UNILEVER, BRF, AMBEV...)

MARCAS_CONHECIDAS: dict[str, dict] = {
    # ── Higiene Pessoal ───────────────────────────────────────────────
    "DOVE":         {"fabricante": "UNILEVER",          "aliases": ["DOVE"],                          "categoria": "higiene"},
    "REXONA":       {"fabricante": "UNILEVER",          "aliases": ["REXONA"],                        "categoria": "higiene"},
    "AXE":          {"fabricante": "UNILEVER",          "aliases": ["AXE"],                           "categoria": "higiene"},
    "SEDA":         {"fabricante": "UNILEVER",          "aliases": ["SEDA"],                          "categoria": "higiene"},
    "LUX":          {"fabricante": "UNILEVER",          "aliases": ["LUX"],                           "categoria": "higiene"},
    "COLGATE":      {"fabricante": "COLGATE-PALMOLIVE", "aliases": ["COLGATE"],                       "categoria": "higiene"},
    "ORAL B":       {"fabricante": "P&G",               "aliases": ["ORAL B", "ORAL-B", "ORALB"],    "categoria": "higiene"},
    "GILLETTE":     {"fabricante": "P&G",               "aliases": ["GILLETTE", "PRESTOBARBA", "PRESTO BARBA"], "categoria": "higiene"},
    "PANTENE":      {"fabricante": "P&G",               "aliases": ["PANTENE"],                       "categoria": "higiene"},
    "HEAD SHOULDERS": {"fabricante": "P&G",             "aliases": ["HEAD SHOULDERS", "HEAD E SHOULDERS"], "categoria": "higiene"},
    "JOHNSON":      {"fabricante": "JOHNSON & JOHNSON", "aliases": ["JOHNSON", "JOHNSONS"],           "categoria": "higiene"},
    # ── Limpeza ───────────────────────────────────────────────────────
    "OMO":          {"fabricante": "UNILEVER",          "aliases": ["OMO"],                           "categoria": "limpeza"},
    "COMFORT":      {"fabricante": "UNILEVER",          "aliases": ["COMFORT"],                       "categoria": "limpeza"},
    "CIFS":         {"fabricante": "UNILEVER",          "aliases": ["CIF", "CIFS"],                   "categoria": "limpeza"},
    "ARIEL":        {"fabricante": "P&G",               "aliases": ["ARIEL"],                         "categoria": "limpeza"},
    "ACE":          {"fabricante": "P&G",               "aliases": ["ACE"],                           "categoria": "limpeza"},
    "DOWNY":        {"fabricante": "P&G",               "aliases": ["DOWNY"],                         "categoria": "limpeza"},
    "YPE":          {"fabricante": "QUIMICA AMPARO",    "aliases": ["YPE", "YPE"],                    "categoria": "limpeza"},
    "VEJA":         {"fabricante": "RECKITT",           "aliases": ["VEJA"],                          "categoria": "limpeza"},
    "LYSOL":        {"fabricante": "RECKITT",           "aliases": ["LYSOL"],                         "categoria": "limpeza"},
    "VANISH":       {"fabricante": "RECKITT",           "aliases": ["VANISH"],                        "categoria": "limpeza"},
    # ── Bebidas ───────────────────────────────────────────────────────
    "COCA COLA":    {"fabricante": "THE COCA-COLA CO",  "aliases": ["COCA", "COCA-COLA", "COCACOLA", "COCA COLA"], "categoria": "bebidas"},
    "PEPSI":        {"fabricante": "PEPSICO",           "aliases": ["PEPSI", "PEPSI-COLA"],           "categoria": "bebidas"},
    "GUARANA ANTARCTICA": {"fabricante": "AMBEV",       "aliases": ["GUARANA ANT", "GUARANA ANTARC"], "categoria": "bebidas"},
    "BRAHMA":       {"fabricante": "AMBEV",             "aliases": ["BRAHMA"],                        "categoria": "bebidas"},
    "SKOL":         {"fabricante": "AMBEV",             "aliases": ["SKOL"],                          "categoria": "bebidas"},
    "ANTARCTICA":   {"fabricante": "AMBEV",             "aliases": ["ANTARCTICA", "ANTARCT", "ANTART"], "categoria": "bebidas"},
    "BOHEMIA":      {"fabricante": "AMBEV",             "aliases": ["BOHEMIA"],                       "categoria": "bebidas"},
    "HEINEKEN":     {"fabricante": "HEINEKEN",          "aliases": ["HEINEKEN", "HEINEK"],            "categoria": "bebidas"},
    "STELLA ARTOIS":{"fabricante": "AMBEV",             "aliases": ["STELLA", "STELLA ARTOIS"],       "categoria": "bebidas"},
    "BUDWEISER":    {"fabricante": "AMBEV",             "aliases": ["BUDWEISER", "BUD"],              "categoria": "bebidas"},
    "ITAIPAVA":     {"fabricante": "PETROPOLIS",        "aliases": ["ITAIPAVA"],                      "categoria": "bebidas"},
    "CRYSTAL":      {"fabricante": "PETROPOLIS",        "aliases": ["CRYSTAL"],                       "categoria": "bebidas"},
    "NESCAFE":      {"fabricante": "NESTLE",            "aliases": ["NESCAFE", "NESCAFE"],            "categoria": "bebidas"},
    # ── Alimentos (frios / proteína) ──────────────────────────────────
    "SADIA":        {"fabricante": "BRF",               "aliases": ["SADIA"],                         "categoria": "frios"},
    "PERDIGAO":     {"fabricante": "BRF",               "aliases": ["PERDIGAO", "PERDIGAO"],          "categoria": "frios"},
    "SEARA":        {"fabricante": "JBS",               "aliases": ["SEARA"],                         "categoria": "frios"},
    "FRIBOI":       {"fabricante": "JBS",               "aliases": ["FRIBOI"],                        "categoria": "frios"},
    "SWIFT":        {"fabricante": "JBS",               "aliases": ["SWIFT"],                         "categoria": "frios"},
    # ── Laticínios ────────────────────────────────────────────────────
    "NESTLE":       {"fabricante": "NESTLE",            "aliases": ["NESTLE", "NESTLE"],              "categoria": "laticinios"},
    "DANONE":       {"fabricante": "DANONE",            "aliases": ["DANONE"],                        "categoria": "laticinios"},
    "YOPRO":        {"fabricante": "DANONE",            "aliases": ["YOPRO", "YO PRO"],               "categoria": "laticinios"},
    "ACTIVIA":      {"fabricante": "DANONE",            "aliases": ["ACTIVIA"],                       "categoria": "laticinios"},
    # ── Panificação / biscoitos ───────────────────────────────────────
    "BAUDUCCO":     {"fabricante": "BAUDUCCO",          "aliases": ["BAUDUCCO"],                      "categoria": "panificacao"},
    "WICKBOLD":     {"fabricante": "WICKBOLD",          "aliases": ["WICKBOLD"],                      "categoria": "panificacao"},
    "PANCO":        {"fabricante": "PANCO",             "aliases": ["PANCO"],                         "categoria": "panificacao"},
    "PULLMAN":      {"fabricante": "BIMBO",             "aliases": ["PULLMAN"],                       "categoria": "panificacao"},
    # ── Grãos / secos ─────────────────────────────────────────────────
    "CAMIL":        {"fabricante": "CAMIL",             "aliases": ["CAMIL"],                         "categoria": "graos"},
    "TIO JOAO":     {"fabricante": "JOSAPAR",           "aliases": ["TIO JOAO", "TIO JOAO"],          "categoria": "graos"},
    "PATRONO":      {"fabricante": "PATRONO",           "aliases": ["PATRONO"],                       "categoria": "graos"},
    # ── Azeites / óleos ───────────────────────────────────────────────
    "ANDORINHA":    {"fabricante": "SOVENA",            "aliases": ["ANDORINHA"],                     "categoria": "alimentos"},
    "GALLO":        {"fabricante": "VICTOR GUEDES",     "aliases": ["GALLO"],                         "categoria": "alimentos"},
    # ── Guloseimas / balas ────────────────────────────────────────────
    "FLAMBOYANT":   {"fabricante": "FLAMBOYANT",        "aliases": ["FLAMBOYANT"],                    "categoria": "alimentos"},
    "ARCOR":        {"fabricante": "ARCOR",             "aliases": ["ARCOR", "BUTTER TOFFEES"],       "categoria": "alimentos"},
    "DOCILE":       {"fabricante": "DOCILE",            "aliases": ["DOCILE"],                        "categoria": "alimentos"},
    "FINI":         {"fabricante": "FINI",              "aliases": ["FINI"],                          "categoria": "alimentos"},
}

# ── Índice base (dicionário fixo) ─────────────────────────────────────────────
# alias (maiúsculas) → nome canônico da marca
_ALIAS_INDEX: dict[str, str] = {}
for _marca, _dados in MARCAS_CONHECIDAS.items():
    _ALIAS_INDEX[_marca.upper()] = _marca
    for _alias in _dados["aliases"]:
        _ALIAS_INDEX[_alias.upper()] = _marca

# ── Extensão carregada do banco ───────────────────────────────────────────────
# Preenchido por carregar_marcas_do_banco(); sobrescreve o índice base se
# houver conflito (banco tem prioridade sobre dicionário fixo).
_ALIAS_INDEX_DB: dict[str, str] = {}
_MARCAS_DB: dict[str, dict] = {}   # nome_canônico → {fabricante, categoria}


def carregar_marcas_do_banco(session) -> None:
    """
    Carrega marcas e fabricantes cadastrados no banco e estende o índice.
    Chame uma vez por sessão (ou após cadastrar novas marcas).
    """
    global _ALIAS_INDEX_DB, _MARCAS_DB
    import json
    from app.models.marca import Marca
    from app.models.fabricante import Fabricante

    _ALIAS_INDEX_DB = {}
    _MARCAS_DB = {}

    rows = (
        session.query(Marca, Fabricante)
        .outerjoin(Fabricante, Marca.fabricante_id == Fabricante.id)
        .filter(Marca.ativo == True)
        .all()
    )
    for marca_obj, fab_obj in rows:
        nome = marca_obj.nome.upper()
        fabricante_nome = fab_obj.nome if fab_obj else None
        categoria = marca_obj.categoria or ""

        _MARCAS_DB[nome] = {"fabricante": fabricante_nome, "categoria": categoria}
        _ALIAS_INDEX_DB[nome] = nome

        if marca_obj.aliases:
            try:
                aliases = json.loads(marca_obj.aliases)
                for alias in aliases:
                    _ALIAS_INDEX_DB[alias.upper()] = nome
            except (ValueError, TypeError):
                pass


def invalidar_cache_marcas() -> None:
    """Limpa o cache de marcas do banco — chamar após cadastrar novas marcas."""
    global _ALIAS_INDEX_DB, _MARCAS_DB
    _ALIAS_INDEX_DB = {}
    _MARCAS_DB = {}


# ── Fuzzy matching (Fase 2) ───────────────────────────────────────────────────
# Threshold: 90 = pega typos comuns (1-2 chars errados) sem false positives.
# Mínimo 5 caracteres no token para evitar falsos em tokens curtos.
_FUZZY_THRESHOLD = 90
_FUZZY_MIN_LEN = 5

# Tokens comuns que NUNCA devem ser testados no fuzzy (causam false positives).
# São atributos, embalagens, tipos de produto ou adjetivos genéricos.
_FUZZY_BLACKLIST: set[str] = {
    "NEUTRO", "NEUTRA", "NATURAL", "NORMAL", "GRANDE", "PEQUENO",
    "BRANCO", "BRANCA", "PRETO", "PRETA", "VERDE", "AMARELO",
    "PREMIUM", "ESPECIAL", "ORIGINAL", "TRADICIONAL", "CLASSICO",
    "LIQUIDO", "LIQUIDA", "SOLIDO", "CREMOSO", "CREMOSA",
    "LACTEA", "LACTEO", "CONDENSADA", "CONDENSADO",
    "CHOCOLATE", "MORANGO", "LARANJA", "LIMAO", "MENTA", "BAUNILHA",
    "SUAVE", "FORTE", "MEDIO", "EXTRA", "SUPER", "ULTRA", "MEGA",
    "INTEGRAL", "DESNATADO", "SEMIDESNATADO", "LIGHT", "DIET",
    "PACOTE", "FARDO", "CAIXA", "SACHE", "POTE", "VIDRO", "LATA",
    "GARRAFA", "BISNAGA", "BANDEJA", "GRANEL", "REFIL",
    "SABONETE", "SHAMPOO", "CONDICIONADOR", "DETERGENTE", "AMACIANTE",
    "CERVEJA", "REFRIGERANTE", "BISCOITO", "MACARRAO", "IOGURTE",
    "PILSEN", "MALTE", "PURO",
    "PRESIDENTE", "FRESCOR", "PAINCO", "INSPIRE", "MONTANHA", "LIMPPANO",
}

try:
    from rapidfuzz import fuzz as _fuzz, process as _process
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False


def _todos_aliases() -> dict[str, str]:
    """Retorna dicionário unificado alias→marca (banco + fixo, banco prioriza)."""
    merged = dict(_ALIAS_INDEX)
    merged.update(_ALIAS_INDEX_DB)
    return merged


def _resolver_fabricante(marca: str) -> str | None:
    """Retorna o fabricante dado o nome canônico da marca."""
    if marca in _MARCAS_DB:
        return _MARCAS_DB[marca]["fabricante"]
    if marca in MARCAS_CONHECIDAS:
        return MARCAS_CONHECIDAS[marca]["fabricante"]
    return None


def identificar_marca_e_fabricante(
    texto: str,
) -> tuple[str | None, str | None, float]:
    """
    Identifica marca e fabricante a partir do texto (já limpo/expandido).

    Busca em dois índices (banco tem prioridade sobre dicionário fixo):
      1. _ALIAS_INDEX_DB  — marcas cadastradas no banco
      2. _ALIAS_INDEX     — dicionário fixo embutido no código

    Fallback: fuzzy matching com RapidFuzz (score >= 85, tokens >= 4 chars).

    Retorna: (marca_canônica, fabricante, score)
      - score 1.0    → match exato por token ou bigrama
      - score 0.85+  → match fuzzy (RapidFuzz)
      - score 0.0    → não identificado
    """
    tokens = texto.upper().split()

    # ── Match exato: bigramas → unigramas ────────────────────────────────────
    for i in range(len(tokens) - 1):
        bigrama = f"{tokens[i]} {tokens[i + 1]}"
        # banco primeiro
        if bigrama in _ALIAS_INDEX_DB:
            marca = _ALIAS_INDEX_DB[bigrama]
            return marca, _resolver_fabricante(marca), 1.0
        if bigrama in _ALIAS_INDEX:
            marca = _ALIAS_INDEX[bigrama]
            return marca, _resolver_fabricante(marca), 1.0

    for token in tokens:
        if token in _ALIAS_INDEX_DB:
            marca = _ALIAS_INDEX_DB[token]
            return marca, _resolver_fabricante(marca), 1.0
        if token in _ALIAS_INDEX:
            marca = _ALIAS_INDEX[token]
            return marca, _resolver_fabricante(marca), 1.0

    # ── Fuzzy matching (fallback) ────────────────────────────────────────────
    if _HAS_RAPIDFUZZ:
        aliases = _todos_aliases()
        alias_keys = list(aliases.keys())
        if not alias_keys:
            return None, None, 0.0

        # Testa bigramas primeiro, depois unigramas (excluindo blacklist)
        candidatos = []
        for i in range(len(tokens) - 1):
            bigrama = f"{tokens[i]} {tokens[i + 1]}"
            if len(bigrama.replace(" ", "")) >= _FUZZY_MIN_LEN:
                candidatos.append(bigrama)
        for token in tokens:
            if len(token) >= _FUZZY_MIN_LEN and token not in _FUZZY_BLACKLIST:
                candidatos.append(token)

        for candidato in candidatos:
            resultado = _process.extractOne(
                candidato, alias_keys, scorer=_fuzz.ratio,
                score_cutoff=_FUZZY_THRESHOLD,
            )
            if resultado:
                alias_match, score_fuzzy, _ = resultado
                # Anti false-positive: comprimento do candidato e do alias
                # devem ser similares (diferença máx. 3 chars)
                if abs(len(candidato) - len(alias_match)) > 3:
                    continue
                marca = aliases[alias_match]
                return marca, _resolver_fabricante(marca), round(score_fuzzy / 100, 2)

    return None, None, 0.0
