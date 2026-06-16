import { Link } from 'react-router-dom'
import { ActionBadge } from '@/components/forecast/ActionBadge'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatScore } from '@/lib/format'
import type { MaterialForecast } from '@/types/contract'

type MaterialVocab = {
  id: string
  name: string
  description: string
  category: string
}

type MaterialHeaderProps = {
  material: MaterialVocab
  forecast?: MaterialForecast
  rank?: number
  score?: number
}

export function MaterialHeader({ material, forecast, rank, score }: MaterialHeaderProps) {
  const latestAction = forecast?.actions.at(-1)

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link to="/" className="hover:text-foreground">
              Forecast
            </Link>{' '}
            / {material.name}
          </p>
          <h1 className="text-2xl font-bold tracking-tight">{material.name}</h1>
          <p className="mt-1 max-w-2xl text-muted-foreground">{material.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {rank !== undefined ? (
            <Badge variant="outline">Rank #{rank}</Badge>
          ) : null}
          {score !== undefined ? (
            <Badge variant="secondary">Score {formatScore(score)}</Badge>
          ) : null}
          <Badge variant="outline">{material.category}</Badge>
        </div>
      </div>
      {forecast ? (
        <p className="text-sm text-muted-foreground">
          Forecast as of {formatDate(forecast.as_of)}
          {latestAction ? (
            <>
              {' '}
              · Latest signal: <ActionBadge action={latestAction.action} className="ml-1 align-middle" />
            </>
          ) : null}
          {' '}
          · {forecast.contributing_ticker_count} contributing{' '}
          {forecast.contributing_ticker_count === 1 ? 'company' : 'companies'}
        </p>
      ) : null}
    </header>
  )
}
