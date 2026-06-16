import { useQuery } from '@tanstack/react-query'
import { fetchForecastSummary } from '../api/endpoints'

export function useForecastSummary() {
  return useQuery({
    queryKey: ['forecast', 'summary'],
    queryFn: fetchForecastSummary,
  })
}
