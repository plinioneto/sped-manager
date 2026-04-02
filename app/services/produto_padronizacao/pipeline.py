from dataclasses import dataclass, field
from typing import Optional

from app.services.produto_padronizacao.limpeza import limpar_descricao
from app.services.produto_padronizacao.dicionarios import expandir_abreviacoes
from app.services.produto_padronizacao.unidades import (
    extrair_unidade,
    formatar_unidade,
    UnidadeMedida,
)
from app.services.produto_padronizacao.identificador import identificar_marca_e_fabricante
from app.services.produto_padronizacao.categorizador import (
    categorizar,
    ResultadoCategorizacao,
)

# Palavras que correspondem a tipos de produto (após expansão das abreviações)
_TIPOS_PRODUTO: set[str] = {
    "REFRIGERANTE", "CERVEJA", "AGUA", "SUCO", "VINHO", "WHISKY", "CACHACA",
    "LEITE", "IOGURTE", "QUEIJO", "MANTEIGA", "MARGARINA", "REQUEIJAO",
    "PRESUNTO", "MORTADELA", "LINGUICA", "FRANGO", "CARNE", "PEIXE", "SALSICHA",
    "ARROZ", "FEIJAO", "MACARRAO", "FARINHA", "ACUCAR", "SAL", "OLEO", "AZEITE",
    "BISCOITO", "PAO", "BOLO", "TORRADA",
    "DETERGENTE", "SABONETE", "SHAMPOO", "CONDICIONADOR", "CREME",
    "DESINFETANTE", "AMACIANTE",
    "CAFE", "CHA", "ACHOCOLATADO", "ENERGETICO",
    "MUSSARELA", "MORTADELA",
}

# Atributos do produto que devem ser extraídos separadamente.
# São removidos da descrição antes da categorização (reduz ruído) e
# recolocados na descrição padronizada final.
_ATRIBUTOS: set[str] = {
    "ZERO", "LIGHT", "DIET", "FIT", "SLIM",
    "INTEGRAL", "DESNATADO", "SEMIDESNATADO",
    "TRADICIONAL", "PREMIUM", "GOURMET", "ARTESANAL",
    "EXTRA FORTE", "FORTE", "SUAVE", "MEDIO",
    "EXTRA VIRGEM", "VIRGEM",
    "INFANTIL", "FEMININO", "MASCULINO",
    "SEM GLUTEN", "SEM LACTOSE", "SEM ACUCAR",
    "VEGANO", "VEGETARIANO", "ORGANICO",
    "NATURAL", "ORIGINAL",
}

# Bigramas de atributo — verificados antes dos unigramas
_ATRIBUTOS_BIGRAMA: set[str] = {a for a in _ATRIBUTOS if " " in a}
_ATRIBUTOS_UNIGRAMA: set[str] = {a for a in _ATRIBUTOS if " " not in a}


def _extrair_atributos(texto: str) -> tuple[list[str], str]:
    """
    Extrai atributos do texto e retorna (lista_atributos, texto_sem_atributos).
    """
    tokens = texto.split()
    encontrados: list[str] = []
    indices_remover: set[int] = set()

    # Bigramas primeiro
    for i in range(len(tokens) - 1):
        bigrama = f"{tokens[i]} {tokens[i + 1]}"
        if bigrama in _ATRIBUTOS_BIGRAMA:
            encontrados.append(bigrama)
            indices_remover.add(i)
            indices_remover.add(i + 1)

    # Unigramas (pula índices já consumidos por bigramas)
    for i, token in enumerate(tokens):
        if i not in indices_remover and token in _ATRIBUTOS_UNIGRAMA:
            encontrados.append(token)
            indices_remover.add(i)

    texto_limpo = " ".join(t for i, t in enumerate(tokens) if i not in indices_remover)
    return encontrados, texto_limpo


_EMBALAGENS: dict[str, str] = {
    "PET":      "PET",
    "LATA":     "LATA",
    "LT":       "LATA",
    "VIDRO":    "VIDRO",
    "VD":       "VIDRO",
    "CAIXA":    "CAIXA",
    "CX":       "CAIXA",
    "SACO":     "SACO",
    "SC":       "SACO",
    "PACOTE":   "PACOTE",
    "PCT":      "PACOTE",
    "POTE":     "POTE",
    "TETRA PAK":"TETRA PAK",
    "TETRA":    "TETRA PAK",
    "TP":       "TETRA PAK",
    "BISNAGA":  "BISNAGA",
    "GARRAFA":  "GARRAFA",
    "GF":       "GARRAFA",
    "BANDEJA":  "BANDEJA",
    "BJ":       "BANDEJA",
    "ENVELOPE": "ENVELOPE",
    "ENV":      "ENVELOPE",
    "TUBO":     "TUBO",
    "TB":       "TUBO",
    "ROLO":     "ROLO",
    "RL":       "ROLO",
    "FARDO":    "FARDO",
    "FD":       "FARDO",
    "GRANEL":   "GRANEL",
}


@dataclass
class ResultadoPadronizacao:
    descricao_original:   str
    descricao_limpa:      str
    descricao_padrao:     str
    marca:                Optional[str]   # "DOVE"
    fabricante:           Optional[str]   # "UNILEVER"
    tipo_embalagem:       Optional[str]   # "PET"
    peso_volume_valor:    Optional[float] # 2000.0
    peso_volume_unidade:  Optional[str]   # "ML"
    tipo_produto:         Optional[str]   # "REFRIGERANTE"
    # Classificação
    categoria_id:         Optional[int]  = None
    categoria_nome:       Optional[str]  = None
    grupo_id:             Optional[int]  = None
    grupo_nome:           Optional[str]  = None
    departamento_id:      Optional[int]  = None
    departamento_nome:    Optional[str]  = None
    score_categoria:      float          = 0.0
    # Controle
    score_confianca:      float          = 0.0
    origem:               str            = "regra"
    revisao_necessaria:   bool           = False


def processar_descricao(
    descricao: str,
    abreviacoes_extra: dict | None = None,
    threshold_revisao: float = 0.65,
    session=None,
) -> ResultadoPadronizacao:
    """
    Fase 1 da pipeline: limpeza + dicionários + extração de atributos + categorização.

    Parâmetros:
        descricao         — descrição original (EFD, XML, PDV, ERP)
        abreviacoes_extra — dicionário complementar por tenant (do banco)
        threshold_revisao — score abaixo disso marca revisao_necessaria=True
        session           — SQLAlchemy session (necessária para categorização;
                            se None, categorização é pulada)
    """
    # 1. Limpeza (inclui remoção de stopwords promocionais)
    limpa = limpar_descricao(descricao)

    # 2. Expansão de abreviações (inclui contextuais: DES, TP)
    expandida = expandir_abreviacoes(limpa, abreviacoes_extra)

    # 3. Extração de atributos (ZERO, LIGHT, INTEGRAL, SEM GLUTEN, etc.)
    atributos, texto_sem_atributos = _extrair_atributos(expandida)

    # 4. Extração de campos estruturados
    um = extrair_unidade(expandida)
    marca, fabricante, score_marca = identificar_marca_e_fabricante(expandida)
    tipo_embalagem = _identificar_embalagem(expandida)
    tipo_produto = _identificar_tipo_produto(expandida)

    # 5. Categorização (usa texto completo para máximo contexto)
    cat: ResultadoCategorizacao | None = None
    if session is not None:
        try:
            cat = categorizar(expandida, session)
        except Exception:
            pass

    # 6. Descrição padronizada (ordem canônica: produto + atributos + embalagem + volume)
    descricao_padrao = _montar_descricao_padrao(
        texto_sem_atributos, um, atributos, tipo_embalagem
    ).lower()

    # 7. Score de confiança geral
    score = _calcular_score(marca, tipo_embalagem, um, expandida)

    return ResultadoPadronizacao(
        descricao_original=descricao,
        descricao_limpa=limpa,
        descricao_padrao=descricao_padrao,
        marca=marca,
        fabricante=fabricante,
        tipo_embalagem=tipo_embalagem,
        peso_volume_valor=float(um.valor) if um else None,
        peso_volume_unidade=um.unidade if um else None,
        tipo_produto=tipo_produto,
        categoria_id=cat.categoria_id if cat else None,
        categoria_nome=cat.categoria_nome if cat else None,
        grupo_id=cat.grupo_id if cat else None,
        grupo_nome=cat.grupo_nome if cat else None,
        departamento_id=cat.departamento_id if cat else None,
        departamento_nome=cat.departamento_nome if cat else None,
        score_categoria=cat.score if cat else 0.0,
        score_confianca=score,
        origem="regra",
        revisao_necessaria=score < threshold_revisao,
    )


# ── Funções auxiliares ────────────────────────────────────────────────────────

def _identificar_embalagem(texto: str) -> Optional[str]:
    tokens = texto.upper().split()
    for token in tokens:
        if token in _EMBALAGENS:
            return _EMBALAGENS[token]
    return None


def _identificar_tipo_produto(texto: str) -> Optional[str]:
    tokens = texto.upper().split()
    # bigramas
    for i in range(len(tokens) - 1):
        bg = f"{tokens[i]} {tokens[i + 1]}"
        if bg in _TIPOS_PRODUTO:
            return bg
    # unigramas
    for token in tokens:
        if token in _TIPOS_PRODUTO:
            return token
    return None


def _remover_tokens_embalagem(texto: str) -> str:
    """Remove tokens de embalagem soltos do texto (ex: VD, CX, PET, LT)."""
    import re
    tokens = texto.split()
    limpo = [t for t in tokens if t.upper() not in _EMBALAGENS]
    return re.sub(r"\s+", " ", " ".join(limpo)).strip()


def _montar_descricao_padrao(
    texto: str,
    um: Optional[UnidadeMedida],
    atributos: list[str] | None = None,
    tipo_embalagem: Optional[str] = None,
) -> str:
    """
    Monta descrição padronizada em ordem canônica:
        [produto / descrição base] [atributos] [embalagem] [volume]

    Exemplo:
        "AZEITE OLIVA ANDORINHA EXTRA VIRGEM VD 250ML"
        → extrair_atributos remove EXTRA VIRGEM → texto_sem_atributos = "AZEITE OLIVA ANDORINHA VD"
        → _montar_descricao_padrao remove VD do base → base = "AZEITE OLIVA ANDORINHA"
        → atributos = ["EXTRA VIRGEM"], tipo_embalagem = "VIDRO", volume = "250ML"
        → resultado = "AZEITE OLIVA ANDORINHA EXTRA VIRGEM VIDRO 250ML"
    """
    import re
    _PATTERN = re.compile(
        r"\b\d+(?:[.,]\d+)?\s*(?:ML|LTS?|CL|KGS?|GRS?|MG|UND?|UNI|UNID|PCS?|CX|DZ|PCT?|RL|PR|FD)\b",
        re.IGNORECASE,
    )
    # 1. Remove padrões de quantidade/volume embutidos no texto
    base = _PATTERN.sub("", texto).strip()
    base = re.sub(r"\s+", " ", base).strip()

    # 2. Remove tokens de embalagem que sobram na base
    #    (serão recolocados canonicamente ao final)
    if tipo_embalagem:
        base = _remover_tokens_embalagem(base)

    # 3. Monta ordem canônica
    partes = [base]
    if atributos:
        partes.append(" ".join(atributos))
    if tipo_embalagem:
        partes.append(tipo_embalagem)
    if um:
        partes.append(formatar_unidade(um))
    return " ".join(p for p in partes if p).strip()


def _calcular_score(marca, tipo_embalagem, um, texto: str) -> float:
    """
    Score simples baseado em quantos atributos foram identificados.
    Escala: 0.50 base + bônus por atributo extraído.
    """
    score = 0.50
    if marca:          score += 0.20
    if tipo_embalagem: score += 0.15
    if um:             score += 0.15
    # Penaliza descrições muito curtas (provável dado incompleto)
    if len(texto.split()) < 2:
        score -= 0.20
    return round(min(score, 1.0), 4)
