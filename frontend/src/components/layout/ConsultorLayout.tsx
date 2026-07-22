import { Outlet } from "react-router-dom"
import { ConsultorSidebar } from "./ConsultorSidebar"
import { useAuth } from "../../context/AuthContext"

export function ConsultorLayout() {
  const { usuario } = useAuth()

  return (
    <div className="min-h-screen flex bg-tremor-background-muted">
      <ConsultorSidebar />
      <div className="flex-1 flex flex-col">
        <header className="bg-tremor-background border-b border-tremor-border px-6 py-4 flex justify-end">
          <span className="text-tremor-content text-tremor-default">{usuario?.nome}</span>
        </header>
        <main className="flex-1 px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
