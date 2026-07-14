import { useState, type FormEvent } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { Card, TextInput, Button, Title, Text } from "@tremor/react"
import { useAuth } from "../context/AuthContext"

export function LoginPage() {
  const { usuario, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  if (usuario) {
    return <Navigate to={usuario.role === "admin" ? "/admin/clientes" : "/dashboard"} replace />
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setCarregando(true)
    try {
      await login(username, password)
      navigate("/", { replace: true })
    } catch {
      setErro("Usuário ou senha inválidos.")
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-tremor-background-muted">
      <Card className="max-w-sm w-full mx-4">
        <Title>SPED Manager</Title>
        <Text className="mb-6">Entre com seu usuário e senha</Text>
        <form onSubmit={handleSubmit} className="space-y-4">
          <TextInput
            placeholder="CNPJ ou e-mail"
            value={username}
            onValueChange={setUsername}
            autoFocus
          />
          <TextInput
            type="password"
            placeholder="Senha"
            value={password}
            onValueChange={setPassword}
          />
          {erro && <Text color="rose">{erro}</Text>}
          <Button type="submit" loading={carregando} className="w-full">
            Entrar
          </Button>
        </form>
      </Card>
    </div>
  )
}
