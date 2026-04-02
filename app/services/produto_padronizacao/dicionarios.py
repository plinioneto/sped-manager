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
    # ── Higiene / perfumaria ──────────────────────────────────────────
    "ABS":          "ABSORVENTE",
    "PROT":         "PROTETOR",
    "DESO":         "DESODORANTE",
    "COND":         "CONDICIONADOR",
    "CREME":        "CREME",
    "CR":           "CREME",
    "ESC":          "ESCOVA",
    "PAST":         "PASTA",
    "XAMPU":        "SHAMPOO",
    "XMP":          "SHAMPOO",
    "ACHOC":        "ACHOCOLATADO",
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
    # ── Bigramas (verificados antes dos unigramas) ────────────────────
    "LEITE INT":    "LEITE INTEGRAL",
    "LEITE SEMI":   "LEITE SEMIDESNATADO",
    "LEITE DESC":   "LEITE DESNATADO",
    "PAPEL HIG":    "PAPEL HIGIENICO",
    "PAPEL HIGIEN": "PAPEL HIGIENICO",
}


def expandir_abreviacoes(texto: str, extras: dict | None = None) -> str:
    """
    Expande abreviações no texto (já deve estar em maiúsculas).
    `extras` permite injetar dicionário complementar (ex: do banco, por tenant).
    Testa bigramas antes de unigramas para cobrir casos como "LEITE INT".
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
        # unigrama
        resultado.append(dicio.get(tokens[i], tokens[i]))
        i += 1
    return " ".join(resultado)
