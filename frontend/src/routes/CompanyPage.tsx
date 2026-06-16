import { useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { AuditPageSkeleton } from '@/components/audit/AuditPageSkeleton'
import { CompanyHeader } from '@/components/audit/CompanyHeader'
import { FilingList } from '@/components/audit/FilingList'
import { ErrorState } from '@/components/shared/ErrorState'
import { useExtractions } from '@/hooks/useExtractions'
import { useManufacturers } from '@/hooks/useManufacturers'
import { NotFoundPage } from './NotFoundPage'

export function CompanyPage() {
  const { ticker = '' } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const normalizedTicker = ticker.toUpperCase()

  const manufacturersQuery = useManufacturers()
  const extractionsQuery = useExtractions({ ticker: [normalizedTicker] })

  if (!ticker) {
    return <NotFoundPage />
  }

  if (manufacturersQuery.isLoading || extractionsQuery.isLoading) {
    return <AuditPageSkeleton />
  }

  const company = manufacturersQuery.data?.companies.find(
    (item) => item.ticker.toUpperCase() === normalizedTicker,
  )

  if (manufacturersQuery.isSuccess && !company) {
    return <NotFoundPage />
  }

  if (manufacturersQuery.isError || extractionsQuery.isError) {
    const message =
      manufacturersQuery.error instanceof Error
        ? manufacturersQuery.error.message
        : extractionsQuery.error instanceof Error
          ? extractionsQuery.error.message
          : undefined

    const retry = () => {
      void queryClient.invalidateQueries({ queryKey: ['universe', 'manufacturers'] })
      void queryClient.invalidateQueries({ queryKey: ['extractions'] })
    }

    return <ErrorState message={message} onRetry={retry} />
  }

  if (!company) {
    return <AuditPageSkeleton />
  }

  const extractions = extractionsQuery.data?.items ?? []

  return (
    <div className="space-y-8">
      <CompanyHeader company={company} />
      <FilingList extractions={extractions} />
    </div>
  )
}
