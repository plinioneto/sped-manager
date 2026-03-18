import re
from datetime import datetime


def extrair_registro_0000(conteudo: str) -> dict:
    for linha in conteudo.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # não remove campos vazios — mantém índices corretos
        campos = linha.split('|')

        if len(campos) > 1 and campos[1] == '0000':
            return {
                'dt_ini':       campos[4],
                'dt_fin':       campos[5],
                'razao_social': campos[6],
                'cnpj':         campos[7],
                'uf':           campos[9],
            }

    raise ValueError("Registro |0000| não encontrado no arquivo EFD.")

# Pega as datas para o nome do arquivo
def formatar_periodo(dt_ini: str, dt_fin: str) -> tuple[str, str]:
    ini = datetime.strptime(dt_ini, '%d%m%Y')
    fin = datetime.strptime(dt_fin, '%d%m%Y')
    # agora inclui o dia: YYYYMMDD
    return ini.strftime('%Y%m%d'), fin.strftime('%Y%m%d')

# Gera o nome padronizado do arquivo.
def gerar_nome_arquivo(cnpj: str, periodo_ini: str, periodo_fin: str) -> str:
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    return f"{cnpj_limpo}_{periodo_ini}_{periodo_fin}.txt"

# Ponto de entrada — recebe o conteúdo do arquivo e retorna os metadados extraídos e o novo nome.
def processar_renomeacao(conteudo: str, nome_original: str) -> dict:

    dados = extrair_registro_0000(conteudo)

    periodo_ini, periodo_fin = formatar_periodo(
        dados['dt_ini'],
        dados['dt_fin']
    )

    novo_nome = gerar_nome_arquivo(
        dados['cnpj'],
        periodo_ini,
        periodo_fin
    )

    return {
        'nome_original': nome_original,
        'novo_nome': novo_nome,
        'cnpj': re.sub(r'\D', '', dados['cnpj']),
        'razao_social': dados['razao_social'],
        'uf': dados['uf'],
        'periodo_ini': periodo_ini,
        'periodo_fin': periodo_fin,
        'dt_ini': dados['dt_ini'],
        'dt_fin': dados['dt_fin'],
    }