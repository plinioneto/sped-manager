import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class UnidadeMedida:
    valor: float
    unidade: str  # normalizada: ML, L, G, KG, UN, etc.


# Aliases → unidade canônica
_CANONICAL: dict[str, str] = {
    # Volume
    "ML": "ML", "MIL": "ML", "MILILITRO": "ML", "MILILITROS": "ML",
    "L":  "L",  "LT": "L",  "LTS": "L",  "LITRO": "L",  "LITROS": "L",
    "CL": "CL",
    # Peso
    "G":  "G",  "GR": "G",  "GRS": "G",  "GRAMA": "G",  "GRAMAS": "G",
    "KG": "KG", "KGS": "KG", "QUILO": "KG", "QUILOS": "KG",
    "MG": "MG",
    # Unidade / contagem
    "UN": "UN", "UND": "UN", "UNI": "UN", "UNID": "UN", "UNIDADE": "UN",
    "PC": "PC", "PCS": "PC", "PECA": "PC", "PECAS": "PC",
    "CX": "CX", "CAIXA": "CX",
    "DZ": "DZ", "DUZIA": "DZ",
    "PT": "PT", "PCT": "PT",
    "RL": "RL", "ROLO": "RL",
    "PR": "PR", "PAR": "PR",
    "FD": "FD", "FARDO": "FD",
}

# Padrão regex: número (inteiro ou decimal) + unidade colada ou separada por espaço
_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(ML|MIL|LTS?|CL|KGS?|GRS?|MG|UND?|UNI|UNID|PCS?|CX|DZ|PCT?|RL|PR|FD)\b",
    re.IGNORECASE,
)


_VALOR_MAXIMO = 100_000  # nenhum produto real pesa/mede isso — acima disso é código colado à unidade


def extrair_unidade(texto: str) -> Optional[UnidadeMedida]:
    """
    Extrai a primeira ocorrência de quantidade + unidade no texto.
    Ex: "COCA COLA PET 2000ML" → UnidadeMedida(2000.0, 'ML')
    Ex: "ARROZ TIPO 1 5KG"    → UnidadeMedida(5.0, 'KG')
    """
    match = _PATTERN.search(texto.upper())
    if not match:
        return None
    valor = float(match.group(1).replace(",", "."))
    if valor > _VALOR_MAXIMO:
        # ex: "COD. 9000000390KG" — código de produto colado à unidade, não uma medida real
        return None
    unidade = _CANONICAL.get(match.group(2).upper(), match.group(2).upper())
    return UnidadeMedida(valor=valor, unidade=unidade)


def formatar_unidade(um: Optional[UnidadeMedida]) -> str:
    """
    Formata para exibição compacta: 2.0 L → '2L', 500.0 ML → '500ML'.
    """
    if not um:
        return ""
    valor = int(um.valor) if um.valor == int(um.valor) else um.valor
    return f"{valor}{um.unidade}"


def remover_unidade_do_texto(texto: str) -> str:
    """Remove a parte quantidade+unidade do texto (para processar o restante)."""
    return _PATTERN.sub("", texto).strip()
