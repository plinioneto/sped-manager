import type { ReactNode } from "react"
import { Card, Text, Metric, Badge, Grid } from "@tremor/react"

type Trend = "up" | "down" | "neutral"

interface SparkPoint {
  value: number
}

interface StatCardProps {
  label: string
  value: string
  delta?: number
  deltaLabel?: string
  sparkData?: SparkPoint[]
  trend?: Trend
  accentColor?: string
  alert?: string
  onClick?: () => void
}

const TREND_COLOR: Record<Trend, string> = {
  up: "#10b981",
  down: "#f43f5e",
  neutral: "#6b7280",
}

function Sparkline({ data, color }: { data: SparkPoint[]; color: string }) {
  if (data.length < 2) return null

  const W = 100
  const H = 32
  const pad = 2
  const vals = data.map((d) => d.value)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const pts = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (W - pad * 2)
    const y = H - pad - ((v - min) / range) * (H - pad * 2)
    return `${x},${y}`
  })
  const areaPath = `M${pts[0]} L${pts.join(" L")} L${W - pad},${H} L${pad},${H} Z`
  const linePath = `M${pts[0]} L${pts.join(" L")}`
  const [lastX, lastY] = pts[pts.length - 1].split(",").map(Number)
  const gradientId = `spark-gradient-${color.replace("#", "")}`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-24 h-8" preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} />
      <circle cx={lastX} cy={lastY} r={2} fill={color} />
    </svg>
  )
}

export function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  sparkData,
  trend = "neutral",
  accentColor,
  alert,
  onClick,
}: StatCardProps) {
  const color = accentColor ?? TREND_COLOR[trend]

  return (
    <Card
      className={onClick ? "cursor-pointer hover:shadow-tremor-dropdown transition-shadow" : undefined}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <Text>{label}</Text>
          <Metric>{value}</Metric>
          {delta !== undefined && (
            <div className="mt-1 flex items-center gap-1">
              <Badge color={trend === "up" ? "emerald" : trend === "down" ? "rose" : "gray"} size="xs">
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)}%
              </Badge>
              {deltaLabel && <Text className="text-xs">{deltaLabel}</Text>}
            </div>
          )}
          {alert && (
            <Badge color="rose" size="xs" className="mt-1">
              {alert}
            </Badge>
          )}
        </div>
        {sparkData && sparkData.length > 1 && <Sparkline data={sparkData} color={color} />}
      </div>
    </Card>
  )
}

export function StatGrid({ children, cols = 4 }: { children: ReactNode; cols?: 2 | 3 | 4 }) {
  return (
    <Grid numItemsSm={2} numItemsLg={cols} className="gap-4">
      {children}
    </Grid>
  )
}

export function useStatDelta(series: number[]): { delta: number; trend: Trend; sparkData: SparkPoint[] } {
  const sparkData = series.map((value) => ({ value }))
  if (series.length < 2) return { delta: 0, trend: "neutral", sparkData }

  const last = series[series.length - 1]
  const prev = series[series.length - 2]
  const delta = prev === 0 ? 0 : ((last - prev) / Math.abs(prev)) * 100
  const trend: Trend = delta > 0 ? "up" : delta < 0 ? "down" : "neutral"

  return { delta, trend, sparkData }
}
