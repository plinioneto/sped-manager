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
    # Compostos com "DE" no meio (ex: "AZEITE DE OLIVA") — ver _identificar_tipo_produto
    "AZEITE OLIVA", "OLEO SOJA", "OLEO CANOLA", "OLEO GIRASSOL", "OLEO COCO",
    "LEITE COCO", "CREME LEITE", "LEITE CONDENSADO",
}

# Termos de categoria genéricos demais para aparecer na descrição final quando
# já existe um tipo_produto mais específico (ex: "BEBIDA" antes de "ENERGETICO").
# Não entra em _STOPWORDS de limpeza.py de propósito — "BEBIDA" ainda precisa
# estar presente para o matching de expandir_abreviacoes() e categorizador.py.
_TERMOS_GENERICOS_REDUNDANTES: set[str] = {"BEBIDA", "BEBIDAS"}

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
    marca, fabricante, score_marca, marca_encontrada = identificar_marca_e_fabricante(expandida)
    tipo_embalagem = _identificar_embalagem(expandida)
    tipo_produto, tipo_produto_encontrado = _identificar_tipo_produto(expandida)

    # 5. Categorização (usa texto completo para máximo contexto)
    cat: ResultadoCategorizacao | None = None
    if session is not None:
        try:
            cat = categorizar(expandida, session)
        except Exception:
            pass

    # 6. Descrição padronizada (ordem canônica: tipo + marca + base + atributos + embalagem + volume)
    descricao_padrao = _montar_descricao_padrao(
        texto_sem_atributos, um, atributos, tipo_embalagem,
        tipo_produto=tipo_produto, tipo_produto_encontrado=tipo_produto_encontrado,
        marca=marca, marca_encontrada=marca_encontrada,
    ).lower()

    # 7. Tokens desconhecidos — salva no banco para revisão futura
    if session is not None:
        try:
            tokens_desc = _coletar_tokens_desconhecidos(
                expandida, marca, tipo_produto, tipo_embalagem, atributos
            )
            _salvar_tokens_desconhecidos(session, tokens_desc, descricao)
        except Exception:
            pass

    # 8. Score de confiança geral
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


def _identificar_tipo_produto(texto: str) -> tuple[Optional[str], Optional[str]]:
    """
    Retorna (tipo_canonico, tipo_encontrado).
    tipo_encontrado é o trecho literal do texto (usado pra remoção da base);
    tipo_canonico é a forma normalizada exibida na descrição padronizada —
    diverge quando o composto tem "DE" no meio, ex: "AZEITE DE OLIVA" no texto
    → tipo_canonico="AZEITE OLIVA", tipo_encontrado="AZEITE DE OLIVA".
    """
    tokens = texto.upper().split()
    # bigramas adjacentes
    for i in range(len(tokens) - 1):
        bg = f"{tokens[i]} {tokens[i + 1]}"
        if bg in _TIPOS_PRODUTO:
            return bg, bg
    # bigramas com "DE" no meio (ex: "AZEITE DE OLIVA" → bate "AZEITE OLIVA")
    for i in range(len(tokens) - 2):
        if tokens[i + 1] == "DE":
            bg = f"{tokens[i]} {tokens[i + 2]}"
            if bg in _TIPOS_PRODUTO:
                return bg, f"{tokens[i]} DE {tokens[i + 2]}"
    # unigramas
    for token in tokens:
        if token in _TIPOS_PRODUTO:
            return token, token
    return None, None


def _remover_tokens_embalagem(texto: str) -> str:
    """Remove tokens de embalagem soltos do texto (ex: VD, CX, PET, LT)."""
    import re
    tokens = texto.split()
    limpo = [t for t in tokens if t.upper() not in _EMBALAGENS]
    return re.sub(r"\s+", " ", " ".join(limpo)).strip()


def _remover_texto(base: str, alvo: Optional[str]) -> str:
    """Remove a primeira ocorrência de `alvo` (uma ou mais palavras) da base."""
    if not alvo:
        return base
    import re
    padrao = re.compile(r"\b" + re.escape(alvo) + r"\b", re.IGNORECASE)
    return re.sub(r"\s+", " ", padrao.sub("", base, count=1)).strip()


def _montar_descricao_padrao(
    texto: str,
    um: Optional[UnidadeMedida],
    atributos: list[str] | None = None,
    tipo_embalagem: Optional[str] = None,
    tipo_produto: Optional[str] = None,
    tipo_produto_encontrado: Optional[str] = None,
    marca: Optional[str] = None,
    marca_encontrada: Optional[str] = None,
) -> str:
    """
    Monta descrição padronizada em ordem canônica:
        [tipo de produto] [marca] [produto / resíduo] [atributos] [embalagem] [volume]

    tipo_produto e marca são extraídos da base e recolocados em posição fixa —
    duas descrições de origem diferente para o mesmo produto (tenants distintos,
    grafias distintas) convergem pro mesmo início de string, mesmo quando o
    resíduo (hoje sem dicionário de sabor/variante) ainda diverge. Subtipos que
    completam o próprio tipo (azeite DE oliva, óleo DE soja) não sobram no
    resíduo — entram em _TIPOS_PRODUTO como composto (ex: "AZEITE OLIVA"),
    reconhecidos por _identificar_tipo_produto mesmo com "DE" no meio do texto
    original; só sabor/variante de marca (ex: "kuat laranja") fica no resíduo,
    que por isso vem depois da marca.

    Exemplo:
        "AZEITE DE OLIVA ANDORINHA EXTRA VIRGEM VD 250ML"
        → tipo_produto="AZEITE OLIVA" (tipo_produto_encontrado="AZEITE DE OLIVA")
        → marca="ANDORINHA" (marca_encontrada="ANDORINHA")
        → extrair_atributos remove EXTRA VIRGEM → texto_sem_atributos = "AZEITE DE OLIVA ANDORINHA VD"
        → remove embalagem (VD), tipo_produto_encontrado e marca → resíduo = ""
        → resultado = "AZEITE OLIVA ANDORINHA EXTRA VIRGEM VIDRO 250ML"
    """
    import re
    # 1. Remove só o trecho de quantidade/volume que foi de fato extraído (não
    #    qualquer coisa que "pareça" quantidade — um produto pode ter mais de
    #    um número com unidade no texto, ex: "50UN 500G", e só um vira `um`).
    base = texto
    if um and um.texto_encontrado:
        base = _remover_texto(base, um.texto_encontrado)
    base = re.sub(r"\s+", " ", base).strip()

    # 2. Remove tokens de embalagem que sobram na base
    #    (serão recolocados canonicamente ao final)
    if tipo_embalagem:
        base = _remover_tokens_embalagem(base)

    # 3. Remove tipo de produto e marca da base — recolocados em posição fixa
    #    abaixo. tipo_produto_encontrado/marca_encontrada são os trechos literais
    #    do texto (podem divergir do valor canônico, ex: "AZEITE DE OLIVA" →
    #    "AZEITE OLIVA"; "COCA" → "COCA COLA").
    base = _remover_texto(base, tipo_produto_encontrado)
    base = _remover_texto(base, marca_encontrada)

    # 3b. Termos de categoria genéricos ("BEBIDA") só são redundância quando já
    #     temos um tipo mais específico (ex: ENERGETICO) pra mostrar no lugar.
    #     Não remove em limpar_descricao() porque "BEBIDA" ainda é usado como
    #     gatilho de contexto em expandir_abreviacoes() e como chave de
    #     categorização em categorizador.py — remover cedo demais quebraria os dois.
    if tipo_produto:
        for termo in _TERMOS_GENERICOS_REDUNDANTES:
            base = _remover_texto(base, termo)

    # 4. Monta ordem canônica
    partes = [tipo_produto, marca, base]
    if atributos:
        partes.append(" ".join(atributos))
    if tipo_embalagem:
        partes.append(tipo_embalagem)
    if um:
        partes.append(formatar_unidade(um))
    return " ".join(p for p in partes if p).strip()


# Tokens curtos ou de infraestrutura que nunca são "desconhecidos" relevantes
_TOKENS_IGNORAR: set[str] = {
    # Preposições / artigos / conectivos
    "DE", "DA", "DO", "DAS", "DOS", "E", "EM", "COM", "SEM", "PARA",
    "POR", "AO", "A", "O", "AS", "OS", "NO", "NA", "NOS", "NAS",
    # Unidades (já cobertas pelo extrator, mas podem sobrar)
    "ML", "LT", "LTS", "L", "KG", "KGS", "GR", "GRS", "MG",
    "UND", "UN", "UNI", "UNID", "PC", "PCS", "CX", "DZ", "PCT",
    "RL", "PR", "FD", "SC",
    # Números isolados
}


def _coletar_tokens_desconhecidos(
    expandida: str,
    marca: str | None,
    tipo_produto: str | None,
    tipo_embalagem: str | None,
    atributos: list[str],
) -> set[str]:
    """
    Retorna tokens da descrição expandida que não foram reconhecidos por
    nenhuma parte do pipeline. Candidatos a enriquecer dicionários futuros.
    """
    import re
    from app.services.produto_padronizacao.dicionarios import ABREVIACOES, ABREVIACOES_CONTEXTUAIS
    from app.services.produto_padronizacao.identificador import _todos_aliases

    # Conjunto de todos os tokens "conhecidos"
    conhecidos: set[str] = set()

    # Valores expandidos de abreviações
    conhecidos.update(v.upper() for v in ABREVIACOES.values())
    conhecidos.update(ABREVIACOES_CONTEXTUAIS.keys())
    # Chaves e valores do vocab de categoria (unigramas)
    for chave in _VOCAB_CATEGORIA:
        conhecidos.update(chave.upper().split())
    for chave in _VOCAB_TIPO_PRODUTO:
        conhecidos.update(chave.upper().split())
    for chave in _VOCAB_HORTIFRUTI:
        conhecidos.update(chave.upper().split())
    # Embalagens
    conhecidos.update(_EMBALAGENS.keys())
    conhecidos.update(v.upper() for v in _EMBALAGENS.values())
    # Atributos
    conhecidos.update(t for a in _ATRIBUTOS for t in a.upper().split())
    # Tipos de produto
    conhecidos.update(t for p in _TIPOS_PRODUTO for t in p.upper().split())
    # Marcas conhecidas (aliases)
    try:
        conhecidos.update(_todos_aliases().keys())
    except Exception:
        pass
    # Resultado da própria detecção
    if marca:
        conhecidos.update(marca.upper().split())
    if tipo_produto:
        conhecidos.update(tipo_produto.upper().split())
    if tipo_embalagem:
        conhecidos.update(tipo_embalagem.upper().split())
    for a in atributos:
        conhecidos.update(a.upper().split())
    # Tokens a ignorar
    conhecidos.update(_TOKENS_IGNORAR)

    # Padrão de número/unidade
    _NUM_PATTERN = re.compile(r"^\d+([.,]\d+)?$")

    desconhecidos: set[str] = set()
    for token in expandida.upper().split():
        if len(token) < 4:
            continue
        if token in conhecidos:
            continue
        if _NUM_PATTERN.match(token):
            continue
        desconhecidos.add(token)

    return desconhecidos


def _salvar_tokens_desconhecidos(
    session,
    tokens: set[str],
    exemplo: str,
) -> None:
    """Faz upsert dos tokens desconhecidos no banco (contagem acumulada)."""
    if not tokens:
        return
    from datetime import datetime
    from app.models.token_desconhecido import TokenDesconhecido

    for token in tokens:
        existing = (
            session.query(TokenDesconhecido)
            .filter(TokenDesconhecido.token == token)
            .first()
        )
        if existing:
            existing.contagem += 1
            existing.ultimo_visto = datetime.utcnow()
        else:
            session.add(TokenDesconhecido(
                token=token,
                contagem=1,
                exemplo=exemplo[:200],
            ))
    try:
        session.commit()
    except Exception:
        session.rollback()


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
