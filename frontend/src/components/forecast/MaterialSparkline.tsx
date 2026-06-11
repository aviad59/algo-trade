import { Link } from 'react-router-dom'
import { Line, LineChart, ResponsiveContainer } from 'recharts'
import { useMaterialForecast } from '@/hooks/useMaterialForecast'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

type MaterialSparklineProps = {
  materialId: string
  name: string
}

export function MaterialSparkline({ materialId, name }: MaterialSparklineProps) {
  const { data, isLoading, isError } = useMaterialForecast(materialId)

  const chartData = data?.curve.map((point) => ({
    month: point.month,
    signal: point.signal,
  }))

  return (
    <Link to={`/materials/${materialId}`} className="block">
      <Card className="h-full border-border/60 transition-colors hover:border-primary/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{name}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-12 w-full" />
          ) : isError || !chartData?.length ? (
            <p className="text-xs text-muted-foreground">No curve data</p>
          ) : (
            <ResponsiveContainer width="100%" height={48}>
              <LineChart data={chartData}>
                <Line
                  type="monotone"
                  dataKey="signal"
                  stroke="var(--color-chart-2)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}
