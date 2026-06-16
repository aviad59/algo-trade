import { useQueryClient } from '@tanstack/react-query'
import { AsOfBanner } from '@/components/forecast/AsOfBanner'
import { DashboardSkeleton } from '@/components/forecast/DashboardSkeleton'
import { MaterialRankingTable } from '@/components/forecast/MaterialRankingTable'
import { MaterialSparklineGrid } from '@/components/forecast/MaterialSparklineGrid'
import { TimingSummaryCards } from '@/components/forecast/TimingSummaryCards'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { useForecastSummary } from '@/hooks/useForecastSummary'
import { useRanking } from '@/hooks/useRanking'

const SPARKLINE_MATERIAL_COUNT = 3
const TIMING_CARD_COUNT = 3

export function DashboardPage() {
  const queryClient = useQueryClient()
  const summaryQuery = useForecastSummary()
  const rankingQuery = useRanking()

  const isLoading = summaryQuery.isLoading || rankingQuery.isLoading
  const isError = summaryQuery.isError || rankingQuery.isError

  const retry = () => {
    void queryClient.invalidateQueries({ queryKey: ['forecast'] })
  }

  if (isLoading) {
    return <DashboardSkeleton />
  }

  if (isError) {
    const message =
      summaryQuery.error instanceof Error
        ? summaryQuery.error.message
        : rankingQuery.error instanceof Error
          ? rankingQuery.error.message
          : undefined
    return <ErrorState message={message} onRetry={retry} />
  }

  const summary = summaryQuery.data
  const ranking = rankingQuery.data

  if (!summary?.top_materials.length || !ranking?.ranked_materials.length) {
    return <EmptyState />
  }

  const topMaterials = summary.top_materials.slice(0, TIMING_CARD_COUNT)
  const sparklineMaterials = summary.top_materials.slice(0, SPARKLINE_MATERIAL_COUNT)

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHeader
        title="Forecast dashboard"
        description="Ranked materials, narrative timing signals, and BUY/SELL summary from SEC filings."
      />

      <AsOfBanner summary={summary} />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Top materials</h2>
        <TimingSummaryCards materials={topMaterials} />
      </section>

      <MaterialSparklineGrid materials={sparklineMaterials} />
      <MaterialRankingTable ranking={ranking} summary={summary} />
    </div>
  )
}
