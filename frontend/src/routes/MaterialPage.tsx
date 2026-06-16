import { useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { ContributorsTable } from '@/components/forecast/ContributorsTable'
import { ForecastChart } from '@/components/forecast/ForecastChart'
import { InstrumentsPanel } from '@/components/forecast/InstrumentsPanel'
import { MaterialHeader } from '@/components/forecast/MaterialHeader'
import { MaterialPageSkeleton } from '@/components/forecast/MaterialPageSkeleton'
import { RankPanel } from '@/components/forecast/RankPanel'
import { SignalDataTable } from '@/components/forecast/SignalDataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { useExtractions } from '@/hooks/useExtractions'
import { useInstruments } from '@/hooks/useInstruments'
import { useMaterialForecast } from '@/hooks/useMaterialForecast'
import { useMaterials } from '@/hooks/useMaterials'
import { useRanking } from '@/hooks/useRanking'
import { NotFoundPage } from './NotFoundPage'

export function MaterialPage() {
  const { materialId = '' } = useParams<{ materialId: string }>()
  const queryClient = useQueryClient()

  const materialsQuery = useMaterials()
  const rankingQuery = useRanking()
  const forecastQuery = useMaterialForecast(materialId)
  const extractionsQuery = useExtractions({ material: materialId })
  const instrumentsQuery = useInstruments(materialId)

  if (!materialId) {
    return <NotFoundPage />
  }

  if (materialsQuery.isLoading) {
    return <MaterialPageSkeleton />
  }

  const material = materialsQuery.data?.materials.find((item) => item.id === materialId)

  if (materialsQuery.isSuccess && !material) {
    return <NotFoundPage />
  }

  const rankingEntry = rankingQuery.data?.ranked_materials.find(
    (item) => item.material_id === materialId,
  )
  const rankIndex = rankingQuery.data?.ranked_materials.findIndex(
    (item) => item.material_id === materialId,
  )

  const isCoreLoading =
    rankingQuery.isLoading || forecastQuery.isLoading || extractionsQuery.isLoading

  if (isCoreLoading || !material) {
    return <MaterialPageSkeleton />
  }

  const retry = () => {
    void queryClient.invalidateQueries({ queryKey: ['forecast'] })
    void queryClient.invalidateQueries({ queryKey: ['extractions'] })
    void queryClient.invalidateQueries({ queryKey: ['universe'] })
  }

  if (rankingQuery.isError || extractionsQuery.isError) {
    const message =
      rankingQuery.error instanceof Error
        ? rankingQuery.error.message
        : extractionsQuery.error instanceof Error
          ? extractionsQuery.error.message
          : undefined
    return <ErrorState message={message} onRetry={retry} />
  }

  const forecast = forecastQuery.isSuccess ? forecastQuery.data : undefined
  const extractions = extractionsQuery.data?.items ?? []
  const instruments = instrumentsQuery.isSuccess ? instrumentsQuery.data : undefined

  return (
    <div className="space-y-8">
      <MaterialHeader
        material={material}
        forecast={forecast}
        rank={rankIndex !== undefined && rankIndex >= 0 ? rankIndex + 1 : undefined}
        score={rankingEntry?.score}
      />

      {forecastQuery.isError ? (
        <ErrorState
          title="Forecast not available"
          message="No signal curve has been generated for this material yet."
          onRetry={retry}
        />
      ) : forecast ? (
        <>
          <ForecastChart forecast={forecast} />
          <SignalDataTable curve={forecast.curve} />
        </>
      ) : null}

      {rankingEntry && rankIndex !== undefined && rankIndex >= 0 ? (
        <RankPanel entry={rankingEntry} rank={rankIndex + 1} />
      ) : null}

      <ContributorsTable extractions={extractions} materialId={materialId} />

      {instruments ? <InstrumentsPanel instruments={instruments} /> : null}
    </div>
  )
}
