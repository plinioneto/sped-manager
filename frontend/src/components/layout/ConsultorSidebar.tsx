import { Link, useLocation } from "react-router-dom"
import { useAuth } from "../../context/AuthContext"
import { useConsultorBrand } from "../../hooks/useConsultorBrand"

const NAV = [
  { to: "/consultor/dashboard", label: "Dashboard" },
  { to: "/consultor/clientes", label: "Clientes" },
]

const SIDEBAR_BG = "#0F1623"

export function ConsultorSidebar() {
  const { logout } = useAuth()
  const { brand } = useConsultorBrand()
  const location = useLocation()
  const corPrimaria = brand?.cor_primaria ?? "#1d4ed8"

  return (
    <aside className="w-64 shrink-0 min-h-screen flex flex-col text-gray-300" style={{ backgroundColor: SIDEBAR_BG }}>
      <div className="px-5 py-6 border-b border-white/10">
        {brand?.logo_url ? (
          <img src={brand.logo_url} alt={brand.nome} className="h-8 mb-2" />
        ) : (
          <span className="text-white font-semibold text-lg">{brand?.nome ?? "Consultor"}</span>
        )}
        {brand?.slogan && <p className="text-xs text-gray-400 mt-1">{brand.slogan}</p>}
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => {
          const active = location.pathname === item.to
          return (
            <Link
              key={item.to}
              to={item.to}
              className="block px-3 py-2 rounded-md text-sm font-medium transition-colors"
              style={
                active
                  ? { backgroundColor: corPrimaria, color: "#fff" }
                  : { color: "#9CA3AF" }
              }
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="px-3 py-4 border-t border-white/10">
        <button onClick={logout} className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-400 hover:text-white hover:bg-white/5">
          Sair
        </button>
      </div>
    </aside>
  )
}
