import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DateRangePicker } from '@/components/explorer/DateRangePicker'
import { ExplorerResultsTabs } from '@/components/explorer/ExplorerResultsTabs'
import { MaterialFilter } from '@/components/explorer/MaterialFilter'
import { ShowResultsButton } from '@/components/explorer/ShowResultsButton'
import { TickerMultiSelect } from '@/components/explorer/TickerMultiSelect'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState } from '@/components/shared/ErrorState'
import { useExtractions } from '@/hooks/useExtractions'
import { useManufacturers } from '@/hooks/useManufacturers'
import { useMaterials } from '@/hooks/useMaterials'
import {
  parseExplorerSearch,
  serializeExplorerParams,
  toExtractionFilters,
  validateExplorerParams,
  type ExplorerParams,
} from '@/lib/explorerParams'

export function ExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const applied = useMemo(
    () => parseExplorerSearch(searchParams.toString()),
    [searchParams],
  )

  const [form, setForm] = useState<ExplorerParams>(applied)
  const [validationError, setValidationError] = useState<string>()

  useEffect(() => {
    setForm(applied)
  }, [applied])

  const manufacturersQuery = useManufacturers()
  const materialsQuery = useMaterials()

  const hasQuery = applied.tickers.length > 0
  const extractionsQuery = useExtractions(toExtractionFilters(applied), {
    enabled: hasQuery,
  })

  const materialNames = Object.fromEntries(
    (materialsQuery.data?.materials ?? []).map((material) => [material.id, material.name]),
  )

  const showResults = () => {
    const validation = validateExplorerParams(form)
    if (!validation.valid) {
      setValidationError(validation.error)
      return
    }

    setValidationError(undefined)
    const query = serializeExplorerParams(form).replace(/^\?/, '')
    setSearchParams(new URLSearchParams(query))
  }

  if (manufacturersQuery.isError || materialsQuery.isError) {
    const message =
      manufacturersQuery.error instanceof Error
        ? manufacturersQuery.error.message
        : materialsQuery.error instanceof Error
          ? materialsQuery.error.message
          : undefined
    return <ErrorState message={message} />
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Explorer</h1>
        <p className="mt-1 text-muted-foreground">
          Query filing extractions by ticker, date range, and optional material filter.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Query</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <TickerMultiSelect
            manufacturers={manufacturersQuery.data?.companies ?? []}
            selected={form.tickers}
            onChange={(tickers) => setForm((current) => ({ ...current, tickers }))}
          />
          <DateRangePicker
            value={{ from: form.from, to: form.to }}
            onChange={(range) =>
              setForm((current) => ({ ...current, from: range.from, to: range.to }))
            }
          />
          <MaterialFilter
            materials={materialsQuery.data?.materials ?? []}
            value={form.material}
            onChange={(material) => setForm((current) => ({ ...current, material }))}
          />
          <div className="flex flex-wrap items-center gap-3">
            <ShowResultsButton onClick={showResults} />
            {validationError ? (
              <p className="text-sm text-destructive">{validationError}</p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {hasQuery ? (
        extractionsQuery.isError ? (
          <ErrorState
            message={
              extractionsQuery.error instanceof Error
                ? extractionsQuery.error.message
                : undefined
            }
            onRetry={() => void extractionsQuery.refetch()}
          />
        ) : (
          <ExplorerResultsTabs
            extractions={extractionsQuery.data?.items ?? []}
            total={extractionsQuery.data?.total ?? 0}
            materialNames={materialNames}
            loading={extractionsQuery.isLoading}
          />
        )
      ) : (
        <p className="text-sm text-muted-foreground">
          Select at least one ticker and click Show results to query extractions.
        </p>
      )}
    </div>
  )
}
