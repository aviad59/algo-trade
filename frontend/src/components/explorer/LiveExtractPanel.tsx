import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { DEMO_TOKEN } from '@/api/config'
import { fetchLiveExtractionStatus, startLiveExtraction } from '@/api/endpoints'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Demo-token holders only: pull a ticker's latest filing through the live
 * pipeline (EDGAR fetch -> Agent #1 -> buffer). Polls job status while
 * running; when the job lands, every query in the app is invalidated so the
 * dashboard, ranking, and backtest visibly update with the new filings.
 */
export function LiveExtractPanel() {
  const queryClient = useQueryClient()
  const [ticker, setTicker] = useState('')
  const [polling, setPolling] = useState(false)
  const wasRunning = useRef(false)

  const statusQuery = useQuery({
    queryKey: ['extract-status'],
    queryFn: fetchLiveExtractionStatus,
    enabled: Boolean(DEMO_TOKEN),
    refetchInterval: polling ? 2000 : false,
  })

  const startMutation = useMutation({
    mutationFn: startLiveExtraction,
    onSuccess: () => {
      setPolling(true)
      void statusQuery.refetch()
    },
  })

  const status = statusQuery.data
  useEffect(() => {
    if (!status) return
    if (status.state === 'running') {
      wasRunning.current = true
      setPolling(true)
      return
    }
    setPolling(false)
    if (wasRunning.current && (status.state === 'done' || status.state === 'error')) {
      wasRunning.current = false
      // new buffer version: let the whole app re-fetch
      void queryClient.invalidateQueries()
    }
  }, [status, queryClient])

  if (!DEMO_TOKEN) return null

  const running = status?.state === 'running' || startMutation.isPending
  const events = status?.events ?? []

  return (
    <Card className="border-emerald-500/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-emerald-400" />
          Pull new filings — live pipeline
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Fetches the ticker&apos;s latest filing from SEC EDGAR and runs Agent #1 on it,
          live. The dashboard, ranking, and backtest update when it lands.
          {status ? ` Budget: ${status.budget_used}/${status.budget_cap} filings.` : ''}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            placeholder="Ticker, e.g. FCX"
            maxLength={10}
            className="h-9 w-40 rounded-lg border border-border/60 bg-background px-3 text-sm uppercase outline-none focus:border-primary"
            disabled={running}
          />
          <Button
            onClick={() => startMutation.mutate(ticker)}
            disabled={running || ticker.trim().length === 0}
          >
            {running ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Extracting…
              </>
            ) : (
              'Run Agent #1'
            )}
          </Button>
          {startMutation.isError && startMutation.error instanceof Error ? (
            <p className="text-sm text-destructive">{startMutation.error.message}</p>
          ) : null}
        </div>
        {events.length > 0 ? (
          <ol className="space-y-1 rounded-lg border border-border/60 bg-background/60 p-3 font-mono text-xs text-muted-foreground">
            {events.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ol>
        ) : null}
        {status?.state === 'error' && status.error ? (
          <p className="text-sm text-destructive">{status.error}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
