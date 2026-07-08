import { useQuery } from "@tanstack/react-query"
import {
  Card, Grid, Metric, Text, Title,
  TabGroup, TabList, Tab, TabPanels, TabPanel,
  AreaChart,
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

function StatCard({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <Card>
      <Text>{titulo}</Text>
      <Metric>{valor}</Metric>
    </Card>
  )
}

export function DashboardPage() {
  const { usuario } = useAuth()
  const temSellIn = usuario?.produtos_ativos?.includes("analise_sell_in") ?? false

  const { data, isLoading } = useQuery({
    queryKey: ["kpis", "mensais"],
    queryFn: async () => (await api.get<KpiMensal[]>("/kpis/mensais")).data,
  })

  if (isLoading) return <Text>Carregando...</Text>

  if (!data || data.length === 0) {
    return (
      <Card>
        <Title>Sem dados disponíveis</Title>
        <Text>Ainda não há KPIs calculados para este cliente.</Text>
      </Card>
    )
  }

  const ultimo = data[data.length - 1]
  const serie = data.map((k) => ({
    mes: `${nomeMes(k.mes)}/${String(k.ano).slice(2)}`,
    Faturamento: Number(k.vl_faturamento),
    Compras: Number(k.vl_compras),
  }))

  return (
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
              <StatCard titulo="Faturamento" valor={formatBRL(ultimo.vl_faturamento)} />
              <StatCard titulo="Compras" valor={formatBRL(ultimo.vl_compras)} />
              <StatCard titulo="Ticket médio" valor={formatBRL(ultimo.ticket_medio)} />
              <StatCard titulo="ICMS a pagar" valor={formatBRL(ultimo.vl_icms_pagar)} />
            </Grid>
            <Grid numItemsSm={2} className="gap-4">
              <StatCard titulo="PIS" valor={formatBRL(ultimo.vl_pis)} />
              <StatCard titulo="COFINS" valor={formatBRL(ultimo.vl_cofins)} />
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
                <StatCard titulo="Valor comprado" valor={formatBRL(ultimo.vl_compras)} />
                <StatCard titulo="Notas de entrada" valor={formatInt(ultimo.qtd_notas_entrada)} />
                <StatCard titulo="ICMS crédito" valor={formatBRL(ultimo.vl_icms_credito)} />
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
  )
}
