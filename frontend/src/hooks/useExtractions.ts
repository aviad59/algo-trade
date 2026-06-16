import { useQuery } from '@tanstack/react-query'
import { fetchExtractions, type ExtractionFilters } from '../api/endpoints'

type UseExtractionsOptions = {
  enabled?: boolean
}

export function useExtractions(filters: ExtractionFilters = {}, options: UseExtractionsOptions = {}) {
  return useQuery({
    queryKey: ['extractions', filters],
    queryFn: () => fetchExtractions(filters),
    enabled: options.enabled ?? true,
  })
}
