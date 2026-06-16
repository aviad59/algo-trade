import { useQuery } from '@tanstack/react-query'
import { fetchInstruments } from '../api/endpoints'

export function useInstruments(materialId: string) {
  return useQuery({
    queryKey: ['universe', 'instruments', materialId],
    queryFn: () => fetchInstruments(materialId),
    enabled: Boolean(materialId),
  })
}
