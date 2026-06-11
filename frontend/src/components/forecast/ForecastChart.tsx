import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Info } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatMonth, formatSignal } from '@/lib/format'
import type { MaterialForecast } from '@/types/contract'

type ChartPoint = {
  month: string
  signal: number
  forward_AUC: number
  action?: 'BUY' | 'SELL'
  rationale?: string
}

type ForecastChartProps = {
  forecast: MaterialForecast
}

function ActionDot(props: {
  cx?: number
  cy?: number
  payload?: ChartPoint
}) {
  const { cx, cy, payload } = props
  if (cx === undefined || cy === undefined || !payload?.action) {
    return null
  }

  const fill = payload.action === 'BUY' ? '#10b981' : '#ef4444'

  return <circle cx={cx} cy={cy} r={8} fill={fill} stroke="#fff" strokeWidth={2} />
}

function ChartTooltip({
  active,
  payload,
  showForwardAuc,
}: {
  active?: boolean
  payload?: Array<{ payload: ChartPoint }>
  showForwardAuc: boolean
}) {
  if (!active || !payload?.length) {
    return null
  }

  const point = payload[0].payload

  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{formatMonth(point.month)}</p>
      <p>Signal: {formatSignal(point.signal)}</p>
      {showForwardAuc ? <p>Forward AUC: {formatSignal(point.forward_AUC)}</p> : null}
      {point.action && point.rationale ? (
        <p className="mt-1 border-t pt-1">
          <span className={point.action === 'BUY' ? 'text-emerald-700' : 'text-destructive'}>
            {point.action}
          </span>
          : {point.rationale}
        </p>
      ) : null}
    </div>
  )
}

export function ForecastChart({ forecast }: ForecastChartProps) {
  const [showForwardAuc, setShowForwardAuc] = useState(false)

  const chartData = useMemo<ChartPoint[]>(() => {
    return forecast.curve.map((point) => {
      const action = forecast.actions.find((item) => item.date.startsWith(point.month))
      return {
        month: point.month,
        signal: point.signal,
        forward_AUC: point.forward_AUC,
        action: action?.action,
        rationale: action?.rationale,
      }
    })
  }, [forecast.actions, forecast.curve])

  return (
    <section className="space-y-4">
      <Alert>
        <Info />
        <AlertTitle>Narrative signal, not price</AlertTitle>
        <AlertDescription>
          The curve reflects aggregated demand language from SEC filings — not market prices or
          trading recommendations.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle>Demand signal curve</CardTitle>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={showForwardAuc}
              onChange={(event) => setShowForwardAuc(event.target.checked)}
              className="size-4 rounded border-input"
            />
            Show forward AUC
          </label>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="month"
                tickFormatter={formatMonth}
                tick={{ fontSize: 12 }}
                stroke="var(--color-muted-foreground)"
              />
              <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
              <Tooltip content={<ChartTooltip showForwardAuc={showForwardAuc} />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="signal"
                name="Signal"
                stroke="var(--color-chart-2)"
                strokeWidth={2}
                dot={<ActionDot />}
                activeDot={{ r: 6 }}
              />
              {showForwardAuc ? (
                <Line
                  type="monotone"
                  dataKey="forward_AUC"
                  name="Forward AUC"
                  stroke="var(--color-chart-4)"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  dot={false}
                />
              ) : null}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </section>
  )
}
