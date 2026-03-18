import re

def formatar_cnpj(cnpj: str) -> str:
    # remove o que não for número
    numeros = re.sub(r'\D', '', cnpj)

    # verifica se tem 14 digitos
    if len(numeros) != 14:
        return cnpj # se estiver inválido retorna o original
    
    # formata com barras, pontos e hifens

    return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"

def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', cnpj)

