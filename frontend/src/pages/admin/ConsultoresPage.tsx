import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell,
  Badge, Button, TextInput,
} from "@tremor/react"
import { api } from "../../lib/api"
import { useToast } from "../../components/ui/ToastProvider"
import { WithEmptyState, EmptyIcons } from "../../components/ui/EmptyState"

interface Consultor {
  id: number
  nome: string
  cnpj: string | null
  telefone: string | null
  logo_url: string | null
  slogan: string | null
  cor_primaria: string | null
  cor_secundaria: string | null
  ativo: boolean
  total_clientes: number
}

const FORM_INICIAL = {
  nome: "",
  usuario_login: "",
  usuario_senha: "",
  cnpj: "",
  telefone: "",
  logo_url: "",
  slogan: "",
  cor_primaria: "#1d4ed8",
  cor_secundaria: "#1e40af",
}

export function ConsultoresPage() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [criando, setCriando] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)

  const { data: consultores, isLoading } = useQuery({
    queryKey: ["admin", "consultores"],
    queryFn: async () => (await api.get<Consultor[]>("/admin/consultores")).data,
  })

  const criar = useMutation({
    mutationFn: async () => api.post("/admin/consultores", form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "consultores"] })
      toast.success("Consultor criado com sucesso")
      setForm(FORM_INICIAL)
      setCriando(false)
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || "Não foi possível criar o consultor")
    },
  })

  const alternarAtivo = useMutation({
    mutationFn: async ({ id, ativo }: { id: number; ativo: boolean }) =>
      api.put(`/admin/consultores/${id}`, { ativo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "consultores"] })
    },
    onError: () => toast.error("Não foi possível atualizar o consultor"),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title>Consultores</Title>
        {!criando && <Button onClick={() => setCriando(true)}>Novo consultor</Button>}
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
                placeholder="E-mail de login"
                value={form.usuario_login}
                onValueChange={(v) => setForm((f) => ({ ...f, usuario_login: v }))}
                required
              />
              <TextInput
                type="password"
                placeholder="Senha"
                value={form.usuario_senha}
                onValueChange={(v) => setForm((f) => ({ ...f, usuario_senha: v }))}
                required
              />
              <TextInput
                placeholder="CNPJ (opcional)"
                value={form.cnpj}
                onValueChange={(v) => setForm((f) => ({ ...f, cnpj: v }))}
              />
              <TextInput
                placeholder="Telefone (opcional)"
                value={form.telefone}
                onValueChange={(v) => setForm((f) => ({ ...f, telefone: v }))}
              />
              <TextInput
                placeholder="Slogan (opcional)"
                value={form.slogan}
                onValueChange={(v) => setForm((f) => ({ ...f, slogan: v }))}
              />
              <TextInput
                placeholder="URL do logo (opcional)"
                value={form.logo_url}
                onValueChange={(v) => setForm((f) => ({ ...f, logo_url: v }))}
              />
              <div className="flex gap-2">
                <label className="flex-1">
                  <span className="text-tremor-label text-tremor-content">Cor primária</span>
                  <input
                    type="color"
                    value={form.cor_primaria}
                    onChange={(e) => setForm((f) => ({ ...f, cor_primaria: e.target.value }))}
                    className="w-full h-9 rounded-tremor-default border border-tremor-border"
                  />
                </label>
                <label className="flex-1">
                  <span className="text-tremor-label text-tremor-content">Cor secundária</span>
                  <input
                    type="color"
                    value={form.cor_secundaria}
                    onChange={(e) => setForm((f) => ({ ...f, cor_secundaria: e.target.value }))}
                    className="w-full h-9 rounded-tremor-default border border-tremor-border"
                  />
                </label>
              </div>
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
          items={consultores}
          loading={isLoading}
          emptyProps={{
            icon: EmptyIcons.consultores,
            title: "Nenhum consultor ainda",
            description: "Crie o primeiro consultor para começar a revender.",
            action: { label: "Novo consultor", onClick: () => setCriando(true) },
          }}
        >
          {(items) => (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Nome</TableHeaderCell>
                  <TableHeaderCell>Clientes</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Ações</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: c.cor_primaria ?? "#1d4ed8" }} />
                      {c.nome}
                    </TableCell>
                    <TableCell>{c.total_clientes}</TableCell>
                    <TableCell>
                      <Badge color={c.ativo ? "emerald" : "gray"}>{c.ativo ? "Ativo" : "Inativo"}</Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => alternarAtivo.mutate({ id: c.id, ativo: !c.ativo })}
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
