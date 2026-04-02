import re
import unicodedata


def limpar_descricao(texto: str) -> str:
    """Pipeline completa de limpeza. Retorna texto normalizado em maiúsculas."""
    if not texto:
        return ""
    texto = texto.upper().strip()
    texto = _remover_acentos(texto)
    texto = _remover_caracteres_especiais(texto)
    texto = _normalizar_espacos(texto)
    return texto


def _remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _remover_caracteres_especiais(texto: str) -> str:
    # Mantém letras, números, espaços, ponto, hífen e barra
    return re.sub(r"[^A-Z0-9\s\.\-\/]", " ", texto)


def _normalizar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()
