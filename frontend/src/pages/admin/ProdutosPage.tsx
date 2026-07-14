import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell, Switch, Text } from "@tremor/react"
import { api } from "../../lib/api"

interface Produto {
  id: number
  slug: string
  nome: string
  descricao: string | null
  ativo: boolean
}

interface Cliente {
  tenant_id: number
  nome: string
  cnpj: string
  ativo: boolean
  produtos: { produto_saas_id: number; slug: string; nome: string; ativo: boolean }[]
}

export function ProdutosPage() {
  const queryClient = useQueryClient()

  const { data: produtos } = useQuery({
    queryKey: ["admin", "produtos"],
    queryFn: async () => (await api.get<Produto[]>("/admin/produtos")).data,
  })

  const { data: clientes, isLoading } = useQuery({
    queryKey: ["admin", "clientes"],
    queryFn: async () => (await api.get<Cliente[]>("/admin/clientes")).data,
  })

  const toggle = useMutation({
    mutationFn: async ({ tenantId, produtoId, ativo }: { tenantId: number; produtoId: number; ativo: boolean }) =>
      api.put(`/admin/clientes/${tenantId}/produtos/${produtoId}`, { ativo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clientes"] })
    },
  })

  return (
    <div className="space-y-6">
      {produtos?.map((produto) => (
        <Card key={produto.id}>
          <Title>{produto.nome}</Title>
          {produto.descricao && <Text className="mb-4">{produto.descricao}</Text>}
          <Table className="mt-4">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Cliente</TableHeaderCell>
                <TableHeaderCell>CNPJ</TableHeaderCell>
                <TableHeaderCell>Ativo para este cliente</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={3}>Carregando...</TableCell>
                </TableRow>
              )}
              {clientes?.map((cliente) => {
                const entitlement = cliente.produtos.find((p) => p.produto_saas_id === produto.id)
                return (
                  <TableRow key={cliente.tenant_id}>
                    <TableCell>{cliente.nome}</TableCell>
                    <TableCell>{cliente.cnpj}</TableCell>
                    <TableCell>
                      <Switch
                        checked={entitlement?.ativo ?? false}
                        onChange={(ativo) =>
                          toggle.mutate({ tenantId: cliente.tenant_id, produtoId: produto.id, ativo })
                        }
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      ))}
    </div>
  )
}
