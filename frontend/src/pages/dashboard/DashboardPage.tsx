import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Card, Grid, Metric, Text, Title,
  TabGroup, TabList, Tab, TabPanels, TabPanel,
  AreaChart, MultiSelect, MultiSelectItem,
} from "@tremor/react"
import { useAuth } from "../../context/AuthContext"
import { api } from "../../lib/api"
import { formatBRL, formatInt, nomeMes } from "../../lib/format"

interface KpiMensal {
  ano: number
  mes: number
  vl_faturamento: string
  qtd_notas_saida: number
  ticket_medio: string
  vl_compras: string
  qtd_notas_entrada: number
  vl_icms_debito: string
  vl_icms_credito: string
  vl_icms_pagar: string
  vl_icms_st: string
  vl_pis: string
  vl_cofins: string
}

const TODOS_OS_MESES = Array.from({ length: 12 }, (_, i) => i + 1)

function StatCard({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <Card>
      <Text>{titulo}</Text>
      <Metric>{valor}</Metric>
    </Card>
  )
}

function somar(itens: KpiMensal[], campo: keyof KpiMensal): number {
  return itens.reduce((acc, k) => acc + Number(k[campo]), 0)
}

export function DashboardPage() {
  const { usuario } = useAuth()
  const temSellIn = usuario?.produtos_ativos?.includes("analise_sell_in") ?? false

  const { data, isLoading } = useQuery({
    queryKey: ["kpis", "mensais"],
    queryFn: async () => (await api.get<KpiMensal[]>("/kpis/mensais")).data,
  })

  const anosDisponiveis = useMemo(
    () => Array.from(new Set((data ?? []).map((k) => k.ano))).sort((a, b) => b - a),
    [data],
  )
  const ultimoDaLista = data && data.length > 0 ? data[data.length - 1] : undefined

  const [anosSelecionados, setAnosSelecionados] = useState<string[] | undefined>(undefined)
  const [mesesSelecionados, setMesesSelecionados] = useState<string[] | undefined>(undefined)

  const anosAtivos = anosSelecionados ?? (ultimoDaLista ? [String(ultimoDaLista.ano)] : [])
  const mesesAtivos = mesesSelecionados ?? (ultimoDaLista ? [String(ultimoDaLista.mes)] : [])

  if (isLoading) return <Text>Carregando...</Text>

  if (!data || data.length === 0) {
    return (
      <Card>
        <Title>Sem dados disponíveis</Title>
        <Text>Ainda não há KPIs calculados para este cliente.</Text>
      </Card>
    )
  }

  const filtrado = data.filter(
    (k) => anosAtivos.includes(String(k.ano)) && mesesAtivos.includes(String(k.mes)),
  )
  const agregado = filtrado.length > 0 ? filtrado : [ultimoDaLista as KpiMensal]

  const totalFaturamento = somar(agregado, "vl_faturamento")
  const totalCompras = somar(agregado, "vl_compras")
  const totalNotasSaida = somar(agregado, "qtd_notas_saida")
  const totalNotasEntrada = somar(agregado, "qtd_notas_entrada")
  const ticketMedio = totalNotasSaida > 0 ? totalFaturamento / totalNotasSaida : 0
  const totalIcmsPagar = somar(agregado, "vl_icms_pagar")
  const totalIcmsCredito = somar(agregado, "vl_icms_credito")
  const totalPis = somar(agregado, "vl_pis")
  const totalCofins = somar(agregado, "vl_cofins")

  const serie = agregado
    .slice()
    .sort((a, b) => a.ano - b.ano || a.mes - b.mes)
    .map((k) => ({
      mes: `${nomeMes(k.mes)}/${String(k.ano).slice(2)}`,
      Faturamento: Number(k.vl_faturamento),
      Compras: Number(k.vl_compras),
    }))

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <MultiSelect
          value={anosAtivos}
          onValueChange={setAnosSelecionados}
          placeholder="Ano"
          className="max-w-xs"
        >
          {anosDisponiveis.map((ano) => (
            <MultiSelectItem key={ano} value={String(ano)}>
              {String(ano)}
            </MultiSelectItem>
          ))}
        </MultiSelect>
        <MultiSelect
          value={mesesAtivos}
          onValueChange={setMesesSelecionados}
          placeholder="Mês"
          className="max-w-xs"
        >
          {TODOS_OS_MESES.map((mes) => (
            <MultiSelectItem key={mes} value={String(mes)}>
              {nomeMes(mes)}
            </MultiSelectItem>
          ))}
        </MultiSelect>
      </div>
      <TabGroup>
        <TabList>
          {[
            <Tab key="geral">Geral</Tab>,
            ...(temSellIn ? [<Tab key="sellin">Análise Sell In</Tab>] : []),
          ]}
        </TabList>
        <TabPanels>
          {/* Geral */}
          <TabPanel>
            <div className="space-y-6 mt-6">
              <Grid numItemsSm={2} numItemsLg={4} className="gap-4">
                <StatCard titulo="Faturamento" valor={formatBRL(totalFaturamento)} />
                <StatCard titulo="Compras" valor={formatBRL(totalCompras)} />
                <StatCard titulo="Ticket médio" valor={formatBRL(ticketMedio)} />
                <StatCard titulo="ICMS a pagar" valor={formatBRL(totalIcmsPagar)} />
              </Grid>
              <Grid numItemsSm={2} className="gap-4">
                <StatCard titulo="PIS" valor={formatBRL(totalPis)} />
                <StatCard titulo="COFINS" valor={formatBRL(totalCofins)} />
              </Grid>
              <Card>
                <Title>Evolução mensal</Title>
                <AreaChart
                  className="mt-4 h-64"
                  data={serie}
                  index="mes"
                  categories={["Faturamento", "Compras"]}
                  colors={["blue", "cyan"]}
                  valueFormatter={(v) => formatBRL(v)}
                  yAxisWidth={90}
                />
              </Card>
            </div>
          </TabPanel>

          {/* Análise Sell In */}
          {temSellIn && (
            <TabPanel>
              <div className="space-y-6 mt-6">
                <Grid numItemsSm={2} numItemsLg={3} className="gap-4">
                  <StatCard titulo="Valor comprado" valor={formatBRL(totalCompras)} />
                  <StatCard titulo="Notas de entrada" valor={formatInt(totalNotasEntrada)} />
                  <StatCard titulo="ICMS crédito" valor={formatBRL(totalIcmsCredito)} />
                </Grid>
                <Card>
                  <Title>Evolução de compras (sell-in)</Title>
                  <AreaChart
                    className="mt-4 h-64"
                    data={serie}
                    index="mes"
                    categories={["Compras"]}
                    colors={["cyan"]}
                    valueFormatter={(v) => formatBRL(v)}
                    yAxisWidth={90}
                  />
                </Card>
              </div>
            </TabPanel>
          )}
        </TabPanels>
      </TabGroup>
    </div>
  )
}
