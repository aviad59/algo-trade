import { useQuery } from '@tanstack/react-query'
import { fetchExtractionById } from '../api/endpoints'

export function useExtraction(extractionId: string) {
  return useQuery({
    queryKey: ['extractions', extractionId],
    queryFn: () => fetchExtractionById(extractionId),
    enabled: Boolean(extractionId),
  })
}
