import { useQuery } from "@tanstack/react-query"
import { Title } from "@tremor/react"
import { api } from "../../lib/api"
import { StatCard, StatGrid } from "../../components/dashboard/StatCard"

interface ConsultorDashboard {
  total_clientes: number
  clientes_ativos: number
  produtos_ativos: number
}

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["consultor", "dashboard"],
    queryFn: async () => (await api.get<ConsultorDashboard>("/consultor/dashboard")).data,
  })

  return (
    <div className="space-y-6">
      <Title>Dashboard</Title>
      {isLoading ? (
        <p className="text-tremor-content">Carregando...</p>
      ) : (
        <StatGrid cols={3}>
          <StatCard label="Total de clientes" value={String(data?.total_clientes ?? 0)} />
          <StatCard label="Clientes ativos" value={String(data?.clientes_ativos ?? 0)} />
          <StatCard label="Produtos ativos" value={String(data?.produtos_ativos ?? 0)} />
        </StatGrid>
      )}
    </div>
  )
}
