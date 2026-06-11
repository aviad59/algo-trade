import { useQuery } from '@tanstack/react-query'
import { fetchExtractions, type ExtractionFilters } from '../api/endpoints'

export function useExtractions(filters: ExtractionFilters = {}) {
  return useQuery({
    queryKey: ['extractions', filters],
    queryFn: () => fetchExtractions(filters),
  })
}
