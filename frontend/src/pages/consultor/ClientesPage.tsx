import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell,
  Badge, Button, TextInput,
} from "@tremor/react"
import { api } from "../../lib/api"
import { useToast } from "../../components/ui/ToastProvider"
import { WithEmptyState, EmptyIcons } from "../../components/ui/EmptyState"

interface Cliente {
  tenant_id: number
  nome: string
  cnpj: string
  ativo: boolean
}

export function ClientesPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [criando, setCriando] = useState(false)
  const [form, setForm] = useState({ nome: "", cnpj: "", usuario_login: "", usuario_senha: "" })

  const { data: clientes, isLoading } = useQuery({
    queryKey: ["consultor", "clientes"],
    queryFn: async () => (await api.get<Cliente[]>("/consultor/clientes")).data,
  })

  const criar = useMutation({
    mutationFn: async () =>
      api.post("/consultor/clientes", {
        nome: form.nome,
        cnpj: form.cnpj,
        usuario_login: form.usuario_login || undefined,
        usuario_senha: form.usuario_senha || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["consultor", "clientes"] })
      queryClient.invalidateQueries({ queryKey: ["consultor", "dashboard"] })
      toast.success("Cliente criado com sucesso")
      setForm({ nome: "", cnpj: "", usuario_login: "", usuario_senha: "" })
      setCriando(false)
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || "Não foi possível criar o cliente")
    },
  })

  const alternarAtivo = useMutation({
    mutationFn: async ({ tenantId, ativo }: { tenantId: number; ativo: boolean }) =>
      api.put(`/consultor/clientes/${tenantId}`, { ativo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["consultor", "clientes"] })
      queryClient.invalidateQueries({ queryKey: ["consultor", "dashboard"] })
    },
    onError: () => toast.error("Não foi possível atualizar o cliente"),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title>Clientes</Title>
        {!criando && <Button onClick={() => setCriando(true)}>Novo cliente</Button>}
      </div>

      {criando && (
        <Card>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              criar.mutate()
            }}
            className="space-y-4"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <TextInput
                placeholder="Nome"
                value={form.nome}
                onValueChange={(v) => setForm((f) => ({ ...f, nome: v }))}
                required
              />
              <TextInput
                placeholder="CNPJ"
                value={form.cnpj}
                onValueChange={(v) => setForm((f) => ({ ...f, cnpj: v }))}
                required
              />
              <TextInput
                placeholder="Login de acesso (opcional)"
                value={form.usuario_login}
                onValueChange={(v) => setForm((f) => ({ ...f, usuario_login: v }))}
              />
              <TextInput
                type="password"
                placeholder="Senha de acesso (opcional)"
                value={form.usuario_senha}
                onValueChange={(v) => setForm((f) => ({ ...f, usuario_senha: v }))}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" loading={criar.isPending}>
                Salvar
              </Button>
              <Button type="button" variant="secondary" onClick={() => setCriando(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <WithEmptyState
          items={clientes}
          loading={isLoading}
          emptyProps={{
            icon: EmptyIcons.clientes,
            title: "Nenhum cliente ainda",
            description: "Crie seu primeiro cliente para começar.",
            action: { label: "Novo cliente", onClick: () => setCriando(true) },
          }}
        >
          {(items) => (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Nome</TableHeaderCell>
                  <TableHeaderCell>CNPJ</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Ações</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((c) => (
                  <TableRow key={c.tenant_id}>
                    <TableCell>{c.nome}</TableCell>
                    <TableCell>{c.cnpj}</TableCell>
                    <TableCell>
                      <Badge color={c.ativo ? "emerald" : "gray"}>{c.ativo ? "Ativo" : "Inativo"}</Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => alternarAtivo.mutate({ tenantId: c.tenant_id, ativo: !c.ativo })}
                      >
                        {c.ativo ? "Desativar" : "Ativar"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </WithEmptyState>
      </Card>
    </div>
  )
}
