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
    # Limpeza
    "DETERGENTE":       "LIMPEZA DE COZINHA",
    "DESINFETANTE":     "LIMPEZA DE CASA",
    "LAVA ROUPA":       "LIMPEZA PARA ROUPAS",
    "LAVA-ROUPA":       "LIMPEZA PARA ROUPAS",
    "AMACIANTE":        "LIMPEZA PARA ROUPAS",
    "AGUA SANITARIA":   "LIMPEZA PARA ROUPAS",
    "ALVEJANTE":        "LIMPEZA PARA ROUPAS",
    "SABAO EM PO":      "LIMPEZA PARA ROUPAS",
    "SABAO LIQUIDO":    "LIMPEZA PARA ROUPAS",
    "INSETICIDA":       "INSETICIDAS",
    # Higiene
    "SABONETE":     "SABONETES",
    "ABSORVENTE":   "ABSORVENTES",
    "PROTETOR SOLAR": "PROTETOR SOLAR, BRONZEADORES E REPELENTES",
    "REPELENTE":    "PROTETOR SOLAR, BRONZEADORES E REPELENTES",
    "DESODORANTE":  "DESODORANTES E COLONIAS",
    "SHAMPOO":      "PRODUTOS CAPILARES",
    "CONDICIONADOR":"PRODUTOS CAPILARES",
    "CREME PENTEAR":"PRODUTOS CAPILARES",
    "PASTA DENTAL": "HIGIENE BUCAL",
    "FITA DENTAL":  "HIGIENE BUCAL",
    "ENXAGUANTE":   "HIGIENE BUCAL",
    "PAPEL HIGIENICO": "PAPEL HIGIENICO",
    "FRALDA":       "SECAO INFANTIL",
    # Mercearia salgada
    "VINAGRE":      "VINAGRES",
    "AZEITE":       "AZEITES",
    "TEMPERO":      "TEMPEROS E MOLHOS",
    "MOLHO":        "TEMPEROS E MOLHOS",
    "MACARRAO":     "MASSAS E SOPAS",
    "MASSA":        "MASSAS E SOPAS",
    "CONSERVA":     "CONSERVAS E ENLATADOS",
    "SARDINHA":     "CONSERVAS E ENLATADOS",
    "ATUM":         "CONSERVAS E ENLATADOS",
    "MILHO ENLATADO": "CONSERVAS E ENLATADOS",
    # Mercearia doce
    "MISTURA BOLO": "CULINARIA DOCE",
    "CHOCOLATE":    "CHOCOLATES",
    "BOMBOM":       "CHOCOLATES",
    "GELEIA":       "GELEIAS",
    "MEL":          "MEL E MELADOS",
    "IOGURTE":      "LATICINIOS",
    "REQUEIJAO":    "LATICINIOS",
    "QUEIJO":       "LATICINIOS",
    "MANTEIGA":     "LATICINIOS",
    "MARGARINA":    "LATICINIOS",
    "CREME DE LEITE": "LATICINIOS",
    # Frios / proteínas
    "PRESUNTO":     "FRIOS / FATIADOS",
    "MORTADELA":    "FRIOS / FATIADOS",
    "MUSSARELA":    "FRIOS / FATIADOS",
    "SALAME":       "FRIOS / FATIADOS",
    "LINGUICA":     "LINGUICA E SALSICHA",
    "SALSICHA":     "LINGUICA E SALSICHA",
    "FRANGO":       "AVES",
    # Bebidas
    "REFRIGERANTE": "REFRIGERANTE",
    "CERVEJA":      "CERVEJAS",
    "VINHO":        "VINHO",
    "WHISKY":       "DESTILADOS",
    "CACHACA":      "DESTILADOS",
    "VODKA":        "DESTILADOS",
    "SUCO":         "SUCOS",
    "AGUA":         "AGUAS",
    "ENERGETICO":   "OUTRAS CATEGORIAS NAO ALCOOLICAS",
    # Perecíveis / Congelados
    "ACAI":         "CONGELADOS",
    "SORVETE":      "CONGELADOS",
    "PICOLE":       "CONGELADOS",
    "GELADINHO":    "CONGELADOS",
    "POLPA":        "CONGELADOS",
    "PAO DE QUEIJO": "CONGELADOS",
    "LASANHA":      "CONGELADOS",
    "HAMBURGUER":   "CONGELADOS",
    "PIZZA":        "CONGELADOS",
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
    "ACHOCOLATADO": "MATINAIS",
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
    # Limpeza para roupas (nomes exatos da tabela categorias)
    "AGUA SANITARIA":   ("AGUA SANITARIA",              None),
    "ALVEJANTE":        ("ALVEJANTES E CLORO",           None),
    "ALVEJANTES":       ("ALVEJANTES E CLORO",           None),
    "SABAO EM PO":      ("SABAO EM PO",                  None),
    "SABAO LIQUIDO":    ("SABAO LIQUIDO",                None),
    "SABAO EM BARRA":   ("SABAO EM BARRA E PASTA",       None),
    "TIRA MANCHAS":     ("CORANTES, TIRA MANCHAS, GOMA", None),
    "AMACIANTE":        ("AMACIANTE DE ROUPA",           None),
    # Congelados — perecíveis do autoserviço
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
