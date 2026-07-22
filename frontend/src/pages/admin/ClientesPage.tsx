import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell,
  Badge, Button, TextInput, Select, SelectItem,
} from "@tremor/react"
import { api } from "../../lib/api"
import { useToast } from "../../components/ui/ToastProvider"

interface Cliente {
  tenant_id: number
  nome: string
  cnpj: string
  ativo: boolean
  consultor_id: number | null
  consultor_nome: string | null
  produtos: { produto_saas_id: number; slug: string; nome: string; ativo: boolean }[]
}

interface Consultor {
  id: number
  nome: string
}

export function ClientesPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [criando, setCriando] = useState(false)
  const [form, setForm] = useState({ nome: "", cnpj: "", consultor_id: "", usuario_login: "", usuario_senha: "" })

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "clientes"],
    queryFn: async () => (await api.get<Cliente[]>("/admin/clientes")).data,
  })

  const { data: consultores } = useQuery({
    queryKey: ["admin", "consultores"],
    queryFn: async () => (await api.get<Consultor[]>("/admin/consultores")).data,
  })

  const criar = useMutation({
    mutationFn: async () =>
      api.post("/admin/clientes", {
        nome: form.nome,
        cnpj: form.cnpj,
        consultor_id: form.consultor_id ? Number(form.consultor_id) : undefined,
        usuario_login: form.usuario_login || undefined,
        usuario_senha: form.usuario_senha || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clientes"] })
      toast.success("Cliente criado com sucesso")
      setForm({ nome: "", cnpj: "", consultor_id: "", usuario_login: "", usuario_senha: "" })
      setCriando(false)
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || "Não foi possível criar o cliente")
    },
  })

  const reatribuirConsultor = useMutation({
    mutationFn: async ({ tenantId, consultorId }: { tenantId: number; consultorId: number | null }) =>
      api.put(`/admin/clientes/${tenantId}`, consultorId === null ? { limpar_consultor: true } : { consultor_id: consultorId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "clientes"] })
    },
    onError: () => toast.error("Não foi possível atualizar o consultor do cliente"),
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
              <Select
                placeholder="Consultor (opcional — cliente direto se vazio)"
                value={form.consultor_id}
                onValueChange={(v) => setForm((f) => ({ ...f, consultor_id: v }))}
              >
                {(consultores ?? []).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nome}
                  </SelectItem>
                ))}
              </Select>
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
        <Table className="mt-4">
          <TableHead>
            <TableRow>
              <TableHeaderCell>Nome</TableHeaderCell>
              <TableHeaderCell>CNPJ</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Consultor</TableHeaderCell>
              <TableHeaderCell>Produtos ativos</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={5}>Carregando...</TableCell>
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
                  <Select
                    value={c.consultor_id ? String(c.consultor_id) : ""}
                    onValueChange={(v) =>
                      reatribuirConsultor.mutate({ tenantId: c.tenant_id, consultorId: v ? Number(v) : null })
                    }
                  >
                    <SelectItem value="">Direto (sem consultor)</SelectItem>
                    {(consultores ?? []).map((cons) => (
                      <SelectItem key={cons.id} value={String(cons.id)}>
                        {cons.nome}
                      </SelectItem>
                    ))}
                  </Select>
                </TableCell>
                <TableCell>
                  {c.produtos.filter((p) => p.ativo).map((p) => p.nome).join(", ") || "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
