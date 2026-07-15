import { useQuery } from '@tanstack/react-query'
import { fetchBacktest } from '../api/endpoints'

export function useBacktest() {
  return useQuery({
    queryKey: ['backtest'],
    queryFn: fetchBacktest,
  })
}
