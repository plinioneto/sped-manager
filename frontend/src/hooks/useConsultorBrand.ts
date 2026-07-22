import { useEffect, useState } from "react"
import { api } from "../lib/api"

export interface ConsultorBrand {
  id: number
  nome: string
  cnpj: string | null
  telefone: string | null
  logo_url: string | null
  slogan: string | null
  cor_primaria: string | null
  cor_secundaria: string | null
  clientes_ativos: number
}

let cache: ConsultorBrand | null = null

export function clearBrandCache() {
  cache = null
}

export function useConsultorBrand() {
  const [brand, setBrand] = useState<ConsultorBrand | null>(cache)
  const [loading, setLoading] = useState(!cache)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (cache) {
      setBrand(cache)
      setLoading(false)
      return
    }
    setLoading(true)
    api
      .get<ConsultorBrand>("/consultor/perfil")
      .then(({ data }) => {
        cache = data
        setBrand(data)
        setError(null)
      })
      .catch(() => setError("Não foi possível carregar o perfil do consultor"))
      .finally(() => setLoading(false))
  }, [tick])

  const refetch = () => {
    cache = null
    setTick((t) => t + 1)
  }

  return { brand, loading, error, refetch }
}
