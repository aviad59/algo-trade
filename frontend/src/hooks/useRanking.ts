import { useQuery } from '@tanstack/react-query'
import { fetchForecastRanking } from '../api/endpoints'

export function useRanking() {
  return useQuery({
    queryKey: ['forecast', 'ranking'],
    queryFn: fetchForecastRanking,
  })
}
