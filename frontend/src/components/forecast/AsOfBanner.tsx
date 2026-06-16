import { Building2, CalendarClock, FileStack } from 'lucide-react'
import { formatDate, formatDateTime } from '@/lib/format'
import type { ForecastSummary } from '@/types/contract'

type AsOfBannerProps = {
  summary: ForecastSummary
}

function StatTile({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof CalendarClock
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
        <Icon className="size-5" />
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  )
}

export function AsOfBanner({ summary }: AsOfBannerProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <StatTile icon={CalendarClock} label="As of" value={formatDate(summary.as_of)} />
      <StatTile
        icon={FileStack}
        label="Pipeline run"
        value={formatDateTime(summary.pipeline_run_at)}
      />
      <StatTile
        icon={Building2}
        label="Coverage"
        value={`${summary.extractions_count} extractions · ${summary.universe_count} companies`}
      />
    </div>
  )
}
