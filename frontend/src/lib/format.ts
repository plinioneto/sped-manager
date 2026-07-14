export function formatBRL(value: string | number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value))
}

export function formatInt(value: string | number): string {
  return new Intl.NumberFormat("pt-BR").format(Number(value))
}

export function nomeMes(mes: number): string {
  const nomes = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
  ]
  return nomes[mes - 1] ?? String(mes)
}
