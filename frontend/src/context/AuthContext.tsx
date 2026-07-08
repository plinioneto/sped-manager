import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { api } from "../lib/api"

type Role = "admin" | "cliente"

interface Me {
  usuario_id: number
  nome: string
  login: string
  role: Role
  tenant_id: number | null
  produtos_ativos?: string[]
}

interface AuthContextValue {
  usuario: Me | null
  carregando: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Me | null>(null)
  const [carregando, setCarregando] = useState(true)

  const carregarMe = async () => {
    const token = localStorage.getItem("token")
    if (!token) {
      setCarregando(false)
      return
    }
    try {
      const { data } = await api.get<Me>("/auth/me")
      setUsuario(data)
    } catch {
      localStorage.removeItem("token")
      setUsuario(null)
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregarMe()
  }, [])

  const login = async (username: string, password: string) => {
    const form = new URLSearchParams()
    form.set("username", username)
    form.set("password", password)
    const { data } = await api.post("/auth/token", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    localStorage.setItem("token", data.access_token)
    await carregarMe()
  }

  const logout = () => {
    localStorage.removeItem("token")
    setUsuario(null)
  }

  return (
    <AuthContext.Provider value={{ usuario, carregando, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>")
  return ctx
}
