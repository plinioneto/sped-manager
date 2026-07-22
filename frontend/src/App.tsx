import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { useAuth } from "./context/AuthContext"
import { ProtectedRoute } from "./components/ProtectedRoute"
import { AppShell } from "./components/AppShell"
import { ConsultorLayout } from "./components/layout/ConsultorLayout"
import { LoginPage } from "./pages/LoginPage"
import { ClientesPage } from "./pages/admin/ClientesPage"
import { ProdutosPage } from "./pages/admin/ProdutosPage"
import { ConsultoresPage } from "./pages/admin/ConsultoresPage"
import { DashboardPage } from "./pages/dashboard/DashboardPage"
import { DashboardPage as ConsultorDashboardPage } from "./pages/consultor/DashboardPage"
import { ClientesPage as ConsultorClientesPage } from "./pages/consultor/ClientesPage"
import { ROTA_POR_ROLE } from "./lib/routes"

const ADMIN_NAV = [
  { to: "/admin/clientes", label: "Clientes" },
  { to: "/admin/consultores", label: "Consultores" },
  { to: "/admin/produtos", label: "Produtos" },
]

const CLIENTE_NAV = [{ to: "/dashboard", label: "Dashboard" }]

function Home() {
  const { usuario, carregando } = useAuth()
  if (carregando) return null
  if (!usuario) return <Navigate to="/login" replace />
  return <Navigate to={ROTA_POR_ROLE[usuario.role] ?? "/login"} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute role="admin" />}>
          <Route element={<AppShell nav={ADMIN_NAV} />}>
            <Route path="/admin/clientes" element={<ClientesPage />} />
            <Route path="/admin/consultores" element={<ConsultoresPage />} />
            <Route path="/admin/produtos" element={<ProdutosPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute role="consultor" />}>
          <Route element={<ConsultorLayout />}>
            <Route path="/consultor/dashboard" element={<ConsultorDashboardPage />} />
            <Route path="/consultor/clientes" element={<ConsultorClientesPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute role="cliente" />}>
          <Route element={<AppShell nav={CLIENTE_NAV} />}>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>
        </Route>

        <Route path="/" element={<Home />} />
        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  )
}
