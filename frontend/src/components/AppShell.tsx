import { Outlet, Link, useLocation } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

export function AppShell({ nav }: { nav: { to: string; label: string }[] }) {
  const { usuario, logout } = useAuth()
  const location = useLocation()

  return (
    <div className="min-h-screen bg-tremor-background-muted">
      <header className="bg-tremor-background border-b border-tremor-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <span className="font-semibold text-tremor-content-strong">SPED Manager</span>
            <nav className="flex gap-4">
              {nav.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={
                    location.pathname === item.to
                      ? "text-tremor-brand font-medium"
                      : "text-tremor-content hover:text-tremor-content-emphasis"
                  }
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-tremor-content text-tremor-default">{usuario?.nome}</span>
            <button
              onClick={logout}
              className="text-tremor-content hover:text-tremor-content-emphasis text-tremor-default"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
