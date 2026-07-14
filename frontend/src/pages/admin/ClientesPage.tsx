import { useQuery } from "@tanstack/react-query"
import { Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell, Badge } from "@tremor/react"
import { api } from "../../lib/api"

interface Cliente {
  tenant_id: number
  nome: string
  cnpj: string
  ativo: boolean
  produtos: { produto_saas_id: number; slug: string; nome: string; ativo: boolean }[]
}

export function ClientesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "clientes"],
    queryFn: async () => (await api.get<Cliente[]>("/admin/clientes")).data,
  })

  return (
    <Card>
      <Title>Clientes</Title>
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Nome</TableHeaderCell>
            <TableHeaderCell>CNPJ</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Produtos ativos</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={4}>Carregando...</TableCell>
            </TableRow>
          )}
          {data?.map((c) => (
            <TableRow key={c.tenant_id}>
              <TableCell>{c.nome}</TableCell>
              <TableCell>{c.cnpj}</TableCell>
              <TableCell>
                <Badge color={c.ativo ? "emerald" : "gray"}>{c.ativo ? "Ativo" : "Inativo"}</Badge>
              </TableCell>
              <TableCell>
                {c.produtos.filter((p) => p.ativo).map((p) => p.nome).join(", ") || "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  )
}
