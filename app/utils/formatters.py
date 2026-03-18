import re

def formatar_cnpj(cnpj: str) -> str:
    numeros = limpar_cnpj(cnpj)
    if len(numeros) != 14:
        return cnpj
    return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"


def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', cnpj)