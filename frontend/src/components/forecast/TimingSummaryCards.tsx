import { Link } from 'react-router-dom'
import { TrendingUp } from 'lucide-react'
import { ActionBadge } from '@/components/forecast/ActionBadge'
import { formatScore, formatSignal } from '@/lib/format'
import type { TopMaterial } from '@/types/contract'

type TimingSummaryCardsProps = {
  materials: TopMaterial[]
}

export function TimingSummaryCards({ materials }: TimingSummaryCardsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {materials.map((material) => (
        <Link
          key={material.material_id}
          to={`/materials/${material.material_id}`}
          className="group block rounded-xl border border-border/60 bg-card p-5 transition-colors hover:border-primary/40 hover:bg-card/90"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <TrendingUp className="size-5" />
            </div>
            <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-muted-foreground">
              Rank #{material.rank}
            </span>
          </div>
          <h3 className="mt-4 font-semibold text-foreground group-hover:text-primary">
            {material.name}
          </h3>
          <div className="mt-3 flex items-end justify-between gap-2">
            <div>
              <p className="text-xs text-muted-foreground">Score</p>
              <p className="text-2xl font-bold tracking-tight">{formatScore(material.score)}</p>
            </div>
            <ActionBadge action={material.latest_action} />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border/50 pt-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Signal</dt>
              <dd className="font-medium">{formatSignal(material.current_signal)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Tickers</dt>
              <dd className="font-medium">{material.supporting_ticker_count}</dd>
            </div>
          </dl>
        </Link>
      ))}
    </div>
  )
}
