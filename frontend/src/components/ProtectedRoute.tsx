import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

export function ProtectedRoute({ role }: { role: "admin" | "cliente" }) {
  const { usuario, carregando } = useAuth()

  if (carregando) return null
  if (!usuario) return <Navigate to="/login" replace />
  if (usuario.role !== role) return <Navigate to="/login" replace />

  return <Outlet />
}
