# Paleta de cores unificada do SPED Manager
# Todas as páginas devem importar daqui para consistência visual.

# Identidade
AZUL = "#2563EB"
AZUL_ESCURO = "#1E3A5F"

# Semântica (significado fixo — não trocar entre páginas)
VERDE = "#10B981"   # receita, entrada, positivo
VERMELHO = "#EF4444"  # despesa, saída, negativo, alerta
AMBAR = "#F59E0B"   # atenção, neutro, pendente

# Sequência para gráficos com múltiplas séries (até 6)
COLOR_SEQ = [AZUL, VERDE, AMBAR, VERMELHO, "#8B5CF6", "#06B6D4"]

# Mapa semântico rápido para uso em go.Bar / go.Scatter coloridos por categoria
COLOR_MAP = {
    "entrada": VERDE,
    "saida": VERMELHO,
    "saída": VERMELHO,
    "positivo": VERDE,
    "negativo": VERMELHO,
    "neutro": AMBAR,
    "destaque": AZUL,
}
