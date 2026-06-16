import { useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { AuditPageSkeleton } from '@/components/audit/AuditPageSkeleton'
import { DatedEffectsTable } from '@/components/audit/DatedEffectsTable'
import { ExtractionCard } from '@/components/audit/ExtractionCard'
import { SecFilingLink } from '@/components/audit/SecFilingLink'
import { SourceSpanHighlight } from '@/components/audit/SourceSpanHighlight'
import { ErrorState } from '@/components/shared/ErrorState'
import { useExtraction } from '@/hooks/useExtraction'
import { useManufacturers } from '@/hooks/useManufacturers'
import { useMaterials } from '@/hooks/useMaterials'
import { NotFoundPage } from './NotFoundPage'

export function FilingPage() {
  const { extractionId = '' } = useParams<{ extractionId: string }>()
  const queryClient = useQueryClient()

  const extractionQuery = useExtraction(extractionId)
  const manufacturersQuery = useManufacturers()
  const materialsQuery = useMaterials()

  if (!extractionId) {
    return <NotFoundPage />
  }

  if (extractionQuery.isLoading) {
    return <AuditPageSkeleton />
  }

  if (extractionQuery.isError) {
    const message =
      extractionQuery.error instanceof Error ? extractionQuery.error.message : undefined

    if (message?.includes('not found')) {
      return <NotFoundPage />
    }

    const retry = () => {
      void queryClient.invalidateQueries({ queryKey: ['extractions', extractionId] })
    }

    return <ErrorState message={message} onRetry={retry} />
  }

  const extraction = extractionQuery.data
  if (!extraction) {
    return <NotFoundPage />
  }

  const company = manufacturersQuery.data?.companies.find(
    (item) => item.ticker.toUpperCase() === extraction.ticker.toUpperCase(),
  )

  const materialNames = Object.fromEntries(
    (materialsQuery.data?.materials ?? []).map((material) => [material.id, material.name]),
  )

  const uniqueSourceSpans = [...new Set(extraction.dated_effects.map((effect) => effect.source_span))]

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="text-sm text-muted-foreground">
          <Link to="/" className="hover:text-foreground">
            Forecast
          </Link>{' '}
          /{' '}
          <Link to={`/companies/${extraction.ticker}`} className="hover:text-foreground">
            {extraction.ticker}
          </Link>{' '}
          / {extraction.id}
        </p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Filing audit</h1>
            <p className="mt-1 text-muted-foreground">
              {company?.name ?? extraction.ticker} · {extraction.filing_type} · {extraction.id}
            </p>
          </div>
          <SecFilingLink url={extraction.filing_url} />
        </div>
      </header>

      <ExtractionCard extraction={extraction} companyName={company?.name} />
      <DatedEffectsTable effects={extraction.dated_effects} materialNames={materialNames} />

      {uniqueSourceSpans.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Source references</h2>
          <div className="space-y-3">
            {uniqueSourceSpans.map((sourceSpan) => (
              <SourceSpanHighlight key={sourceSpan} sourceSpan={sourceSpan} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
