# Dicionário base de abreviações → expansão.
# Chave: abreviação em maiúsculas (unigrama ou bigrama).
# Valor: forma expandida em maiúsculas.
# Mantido aqui para fácil manutenção; futuramente pode ser complementado
# com registros da tabela `abreviacoes` do banco.

ABREVIACOES: dict[str, str] = {
    # ── Tipos de produto ──────────────────────────────────────────────
    "REFRIG":       "REFRIGERANTE",
    "REFRI":        "REFRIGERANTE",
    "CERV":         "CERVEJA",
    "LING":         "LINGUICA",
    "BISC":         "BISCOITO",
    "BOLACHA":      "BISCOITO",
    "SAB":          "SABONETE",
    "SABO":         "SABONETE",
    "DET":          "DETERGENTE",
    "DESINF":       "DESINFETANTE",
    "LIQ":          "LIQUIDO",
    "LAV":          "LAVA",
    "POL":          "POLVILHO",
    "MARG":         "MARGARINA",
    "MANT":         "MANTEIGA",
    "MORT":         "MORTADELA",
    "PRES":         "PRESUNTO",
    "MUSS":         "MUSSARELA",
    "MUSSA":        "MUSSARELA",
    "QUEIJ":        "QUEIJO",
    "REQUEIJ":      "REQUEIJAO",
    "IOGUR":        "IOGURTE",
    "FAR":          "FARINHA",
    "ARR":          "ARROZ",
    "FEI":          "FEIJAO",
    "ACU":          "ACUCAR",
    "OLE":          "OLEO",
    "VINA":         "VINAGRE",
    "FRA":          "FRANGO",
    "FRANG":        "FRANGO",
    "AMACIANTE":    "AMACIANTE",
    "AMAC":         "AMACIANTE",
    "ACAI":         "ACAI",
    # ── Alimentos / produtos específicos ─────────────────────────────
    "MIST":         "MISTURA",
    "MIXT":         "MISTURA",
    "CONG":         "CONGELADO",
    "EMBU":         "EMBUTIDO",
    "ENERG":        "ENERGETICO",
    "ISOT":         "ISOTONICO",
    "SALG":         "SALGADINHO",
    "RECH":         "RECHEADO",
    "ROSQ":         "ROSQUINHA",
    "BOV":          "BOVINO",
    "PROV":         "PROVOLONE",
    "FILE":         "FILE",
    "MAC":          "MACARRAO",
    "CHOC":         "CHOCOLATE",
    "APERIT":       "APERITIVO",
    "CAFE":         "CAFE",
    "TEMP":         "TEMPERO",
    "IOG":          "IOGURTE",
    "DESNAT":       "DESNATADO",
    "PAO":          "PAO",
    # ── Higiene / perfumaria ──────────────────────────────────────────
    "ABS":          "ABSORVENTE",
    "PROT":         "PROTETOR",
    "DESO":         "DESODORANTE",
    "DESOD":        "DESODORANTE",
    "COND":         "CONDICIONADOR",
    "CREME":        "CREME",
    "CR":           "CREME",
    "ESC":          "ESCOVA",
    "PAST":         "PASTA",
    "XAMPU":        "SHAMPOO",
    "XMP":          "SHAMPOO",
    "ACHOC":        "ACHOCOLATADO",
    "ESM":          "ESMALTE",
    "TINT":         "TINTURA",
    "PERF":         "PERFUME",
    "INSET":        "INSETICIDA",
    "AP BARBEAR":   "APARELHO DE BARBEAR",
    "AP BAR":       "APARELHO DE BARBEAR",
    "AP PREST":     "APARELHO DE BARBEAR",
    "ODORIZ":       "ODORIZADOR",
    "ACUM ELETRICO": "ACUMULADOR ELETRICO",
    "ACUM":          "ACUMULADOR ELETRICO",
    # ── Atributos / qualidade ─────────────────────────────────────────
    "INT":          "INTEGRAL",
    "INTEG":        "INTEGRAL",
    "DESC":         "DESNATADO",
    "SEMI":         "SEMIDESNATADO",
    "DIET":         "DIET",
    "LIGHT":        "LIGHT",
    "TRAD":         "TRADICIONAL",
    "ORIG":         "ORIGINAL",
    "T1":           "TIPO 1",
    "T2":           "TIPO 2",
    "ESP":          "ESPECIAL",
    "FAT":          "FATIADO",
    "INST":         "INSTANTANEO",
    # ── Bigramas (verificados antes dos unigramas) ────────────────────
    "LEITE INT":    "LEITE INTEGRAL",
    "LEITE SEMI":   "LEITE SEMIDESNATADO",
    "LEITE DESC":   "LEITE DESNATADO",
    "SEMI DESNAT":  "SEMIDESNATADO",
    "PAPEL HIG":    "PAPEL HIGIENICO",
    "PAPEL HIGIEN": "PAPEL HIGIENICO",
    "PAO FORM":     "PAO DE FORMA",
    "EXT TOMATE":   "EXTRATO DE TOMATE",
    "MOLHO TOM":    "MOLHO DE TOMATE",
    "CREME DENT":   "CREME DENTAL",
    "PASTA DENT":   "CREME DENTAL",
    "FIO DENT":     "FIO DENTAL",
    "OLEO SOJ":     "OLEO DE SOJA",
    "SAB PO":       "SABAO EM PO",
    "SAB LIQ":      "SABAO LIQUIDO",
    "SAB BARRA":    "SABAO EM BARRA",
    "AG SANIT":     "AGUA SANITARIA",
    "PROT SOL":     "PROTETOR SOLAR",
    "CREME PENT":   "CREME PENTEAR",
    "CREME TRAT":   "CREME TRATAMENTO",
    "MASC CAP":     "MASCARA CAPILAR",
    "MAC INST":     "MACARRAO INSTANTANEO",
    "ATIV CACHOS":  "ATIVADOR DE CACHOS",
    "SAND HAV":     "SANDALIA HAVAIANA",
    "BEB LACTEA":   "BEBIDA LACTEA",
    "GELAT":        "GELATINA",
    "SORV":         "SORVETE",
    "REF PO":       "REFRESCO EM PO",
    "WHISKEY":      "WHISKY",
    "WHISK":        "WHISKY",
    "SARD":         "SARDINHA",
    "PLAST":        "PLASTICO",
    "BEB":          "BEBIDA",
    "AMANT":        "AMANTEIGADO",
    "BISC":         "BISCOITO",
    "DESENG":       "DESENGORDURANTE",
    "LIMP":         "LIMPADOR",
    "PRESERV":      "PRESERVATIVO",
    "SH":           "SHAMPOO",
    "DES":          "DESODORANTE",
    "HIDRAT":       "HIDRATANTE",
    "ENX":          "ENXAGUANTE",
    "LAMP":         "LAMPADA",
    "SAND":         "SANDALIA",
    # ── Expansões adicionais ──────────────────────────────────────────
    "EMPAN":        "EMPANADO",
    "TRAT":         "TRATAMENTO",
    "AERO":         "AEROSOL",
    "MASC":         "MASCARA",
    "PENT":         "PENTEAR",
    "CAPIL":        "CAPILAR",
}


# ── Abreviações contextuais ───────────────────────────────────────────────────
# Termos ambíguos cuja expansão depende das palavras vizinhas.
# Formato: token → lista de (contextos, expansão).
# A primeira regra cujo contexto tenha interseção com os tokens vizinhos vence.
# Se nenhuma regra bater, o token fica inalterado (não expande).
ABREVIACOES_CONTEXTUAIS: dict[str, list[tuple[list[str], str]]] = {
    "DES": [
        (["LEITE", "IOGURTE", "IOGUR", "IOG", "REQUEIJAO", "REQUEIJ",
          "BEBIDA", "LACTEA", "COALHADA"], "DESNATADO"),
        (["REXONA", "DOVE", "NIVEA", "AEROSOL", "AERO", "ROLL", "ROLLON",
          "SPRAY", "COLONIA", "PERFUME", "AXE", "ABOVE", "BOZZANO",
          "MONANGE", "ADIDAS", "GIOVANNA", "HERBISSIMO", "MOOD",
          "MARCHAND", "AVON", "ANTITRANSPIRANTE"], "DESODORANTE"),
        (["VEJA", "PINHO", "LIMPEZA", "LYSOL", "SANIT", "BANHEIRO",
          "MULTIUSO", "PISO"], "DESINFETANTE"),
    ],
    "TP": [
        (["LEITE", "SUCO", "BEBIDA", "CHA", "AGUA", "ACHOCOLATADO",
          "CAPPUCCINO"], "TETRA PAK"),
    ],
}

# Janela de tokens vizinhos para contexto (antes e depois do token ambíguo)
_JANELA_CONTEXTO = 4


def expandir_abreviacoes(texto: str, extras: dict | None = None) -> str:
    """
    Expande abreviações no texto (já deve estar em maiúsculas).
    `extras` permite injetar dicionário complementar (ex: do banco, por tenant).
    Testa bigramas antes de unigramas para cobrir casos como "LEITE INT".
    Termos ambíguos (DES, TP) usam contexto de palavras vizinhas.
    """
    dicio = {**ABREVIACOES, **(extras or {})}
    tokens = texto.split()
    resultado: list[str] = []
    i = 0
    while i < len(tokens):
        # tenta bigrama primeiro
        if i + 1 < len(tokens):
            bigrama = f"{tokens[i]} {tokens[i + 1]}"
            if bigrama in dicio:
                resultado.append(dicio[bigrama])
                i += 2
                continue
        # abreviação contextual (token ambíguo)
        if tokens[i] in ABREVIACOES_CONTEXTUAIS:
            expandido = _resolver_contexto(tokens, i)
            resultado.append(expandido)
            i += 1
            continue
        # unigrama normal
        resultado.append(dicio.get(tokens[i], tokens[i]))
        i += 1
    return " ".join(resultado)


def _resolver_contexto(tokens: list[str], pos: int) -> str:
    """
    Resolve abreviação contextual olhando tokens vizinhos.
    Retorna a expansão se encontrar contexto, senão retorna o token original.
    """
    token = tokens[pos]
    regras = ABREVIACOES_CONTEXTUAIS[token]
    # Coleta vizinhos dentro da janela
    inicio = max(0, pos - _JANELA_CONTEXTO)
    fim = min(len(tokens), pos + _JANELA_CONTEXTO + 1)
    vizinhos = set(tokens[inicio:fim]) - {token}
    for contextos, expansao in regras:
        if vizinhos & set(contextos):
            return expansao
    return token  # sem contexto, mantém original
