import { useQueryClient } from '@tanstack/react-query'
import { Wallet } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ErrorState } from '@/components/shared/ErrorState'
import { useBacktest } from '@/hooks/useBacktest'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Backtest, BacktestResult } from '@/types/contract'

function formatPct(value: number, { signed = true }: { signed?: boolean } = {}): string {
  const pct = (value * 100).toFixed(1)
  return `${signed && value > 0 ? '+' : ''}${pct}%`
}

function pctClass(value: number): string {
  if (value > 0) return 'text-emerald-400'
  if (value < 0) return 'text-red-400'
  return 'text-muted-foreground'
}

function StatCard({ label, value, valueClass, hint }: {
  label: string
  value: string
  valueClass?: string
  hint?: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <div className={cn('text-2xl font-semibold tabular-nums', valueClass)}>{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{label}</div>
      {hint ? <div className="mt-0.5 text-xs text-muted-foreground/70">{hint}</div> : null}
    </div>
  )
}

function OpenPositions({ results }: { results: BacktestResult[] }) {
  const open = results.filter((r) => r.open_position)
  if (!open.length) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-4 text-sm text-muted-foreground">
        No open positions — the strategy is fully in cash as of the window end.
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {open.map((r) => {
        const p = r.open_position!
        return (
          <div
            key={r.sector}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-4"
          >
            <Wallet className="size-5 text-emerald-400" />
            <div className="font-medium">
              Holding {r.sector} <span className="text-muted-foreground">({r.instrument})</span>
            </div>
            <div className="text-sm text-muted-foreground">
              since {formatDate(p.entry_date)} @ {p.entry_price.toFixed(2)}
            </div>
            <div className="text-sm text-muted-foreground">
              now {p.current_price.toFixed(2)}
            </div>
            <div className={cn('ml-auto font-semibold tabular-nums', pctClass(p.return_pct))}>
              {formatPct(p.return_pct)} unrealized
            </div>
          </div>
        )
      })}
    </div>
  )
}

function SectorTable({ backtest }: { backtest: Backtest }) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Per-sector results</h2>
      <div className="overflow-x-auto rounded-xl border border-border/60 bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sector</TableHead>
              <TableHead>ETF</TableHead>
              <TableHead className="text-right">Strategy</TableHead>
              <TableHead className="text-right">Buy &amp; hold</TableHead>
              <TableHead className="text-right">Alpha</TableHead>
              <TableHead className="text-right">Time in market</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {backtest.results.map((r) => (
              <TableRow key={r.sector}>
                <TableCell className="font-medium">{r.sector}</TableCell>
                <TableCell className="text-muted-foreground">{r.instrument}</TableCell>
                <TableCell className={cn('text-right tabular-nums', pctClass(r.return_pct))}>
                  {formatPct(r.return_pct)}
                </TableCell>
                <TableCell className={cn('text-right tabular-nums', pctClass(r.benchmark_pct))}>
                  {formatPct(r.benchmark_pct)}
                </TableCell>
                <TableCell className={cn('text-right tabular-nums', pctClass(r.alpha_pct))}>
                  {formatPct(r.alpha_pct)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {formatPct(r.exposure_pct, { signed: false })}
                </TableCell>
                <TableCell>
                  {r.open_position ? (
                    <Badge className="border-emerald-500/50 bg-emerald-500/10 text-emerald-400">
                      holding
                    </Badge>
                  ) : (
                    <Badge variant="outline">in cash</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}

function TradeBlotter({ backtest }: { backtest: Backtest }) {
  const trades = backtest.results.flatMap((r) =>
    r.trades.map((t) => ({ ...t, sector: r.sector, instrument: r.instrument })),
  )
  trades.sort((a, b) => a.entry_date.localeCompare(b.entry_date))
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Trade blotter</h2>
      <div className="overflow-x-auto rounded-xl border border-border/60 bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sector</TableHead>
              <TableHead>ETF</TableHead>
              <TableHead>Bought</TableHead>
              <TableHead className="text-right">@</TableHead>
              <TableHead>Sold</TableHead>
              <TableHead className="text-right">@</TableHead>
              <TableHead className="text-right">Return</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.map((t) => (
              <TableRow key={`${t.sector}-${t.entry_date}`}>
                <TableCell className="font-medium">{t.sector}</TableCell>
                <TableCell className="text-muted-foreground">{t.instrument}</TableCell>
                <TableCell>{formatDate(t.entry_date)}</TableCell>
                <TableCell className="text-right tabular-nums">{t.entry_price.toFixed(2)}</TableCell>
                <TableCell>
                  {t.open_at_end ? (
                    <span className="text-emerald-400">still holding</span>
                  ) : (
                    formatDate(t.exit_date)
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">{t.exit_price.toFixed(2)}</TableCell>
                <TableCell className={cn('text-right tabular-nums', pctClass(t.return_pct))}>
                  {formatPct(t.return_pct)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}

export function BacktestPage() {
  const queryClient = useQueryClient()
  const query = useBacktest()

  if (query.isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="h-8 w-64 animate-pulse rounded-lg bg-secondary/60" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-secondary/60" />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-xl bg-secondary/60" />
      </div>
    )
  }

  if (query.isError) {
    const message = query.error instanceof Error ? query.error.message : undefined
    return (
      <ErrorState
        message={message}
        onRetry={() => void queryClient.invalidateQueries({ queryKey: ['backtest'] })}
      />
    )
  }

  const backtest = query.data
  if (!backtest) return null

  if (!backtest.available || !backtest.overall) {
    return (
      <div className="mx-auto max-w-7xl space-y-6">
        <PageHeader
          title="Backtest"
          description="Walk-forward replay of the BUY/SELL timer against real ETF prices."
        />
        <div className="rounded-xl border border-border/60 bg-card p-6 text-sm text-muted-foreground">
          Backtest unavailable: {backtest.reason ?? 'unknown reason'}
        </div>
      </div>
    )
  }

  const overall = backtest.overall
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHeader
        title="Backtest"
        description={`Walk-forward replay ${formatDate(backtest.since)} → ${formatDate(backtest.until)} — every decision sees only filings already published. No look-ahead.`}
      />

      <section className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard
          label="Win rate"
          value={formatPct(overall.win_rate, { signed: false })}
          hint={`${overall.winners} of ${overall.trades_closed} closed trades`}
        />
        <StatCard
          label="Strategy return"
          value={formatPct(overall.return_pct)}
          valueClass={pctClass(overall.return_pct)}
          hint="equal-weighted across sectors"
        />
        <StatCard
          label="Buy &amp; hold"
          value={formatPct(overall.benchmark_pct)}
          valueClass={pctClass(overall.benchmark_pct)}
          hint="same instruments, held all window"
        />
        <StatCard
          label="Alpha"
          value={formatPct(overall.alpha_pct)}
          valueClass={pctClass(overall.alpha_pct)}
          hint="strategy minus hold, in points"
        />
        <StatCard
          label="Time in market"
          value={formatPct(overall.exposure_pct, { signed: false })}
          hint="in cash the rest of the window"
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Open positions</h2>
        <OpenPositions results={backtest.results} />
      </section>

      <SectorTable backtest={backtest} />
      <TradeBlotter backtest={backtest} />

      <div className="rounded-xl border border-border/60 bg-card p-4 text-xs leading-relaxed text-muted-foreground">
        <span className="font-medium text-foreground">How to read this.</span> The strategy holds
        cash outside BUY→SELL spans while the benchmark stays invested all window, so negative
        alpha in a rising market is opportunity cost, not a loss. Decisions are replayed
        point-in-time: each month's signal uses only filings published on or before it. Narrative
        research signal — not financial advice.
      </div>
    </div>
  )
}
