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
    "GILLETTE":     {"fabricante": "P&G",               "aliases": ["GILLETTE"],                      "categoria": "higiene"},
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


def identificar_marca_e_fabricante(
    texto: str,
) -> tuple[str | None, str | None, float]:
    """
    Identifica marca e fabricante a partir do texto (já limpo/expandido).

    Busca em dois índices (banco tem prioridade sobre dicionário fixo):
      1. _ALIAS_INDEX_DB  — marcas cadastradas no banco
      2. _ALIAS_INDEX     — dicionário fixo embutido no código

    Retorna: (marca_canônica, fabricante, score)
      - score 1.0  → match exato por token ou bigrama
      - score 0.0  → não identificado
    """
    tokens = texto.upper().split()

    # Bigramas antes de unigramas (ex: "COCA COLA", "ORAL B", "TIO JOAO")
    for i in range(len(tokens) - 1):
        bigrama = f"{tokens[i]} {tokens[i + 1]}"
        # banco primeiro
        if bigrama in _ALIAS_INDEX_DB:
            marca = _ALIAS_INDEX_DB[bigrama]
            fabricante = _MARCAS_DB[marca]["fabricante"]
            return marca, fabricante, 1.0
        if bigrama in _ALIAS_INDEX:
            marca = _ALIAS_INDEX[bigrama]
            fabricante = MARCAS_CONHECIDAS[marca]["fabricante"]
            return marca, fabricante, 1.0

    for token in tokens:
        if token in _ALIAS_INDEX_DB:
            marca = _ALIAS_INDEX_DB[token]
            fabricante = _MARCAS_DB[marca]["fabricante"]
            return marca, fabricante, 1.0
        if token in _ALIAS_INDEX:
            marca = _ALIAS_INDEX[token]
            fabricante = MARCAS_CONHECIDAS[marca]["fabricante"]
            return marca, fabricante, 1.0

    return None, None, 0.0
