import { useQuery } from '@tanstack/react-query'
import { fetchMaterialsList } from '../api/endpoints'

export function useMaterials() {
  return useQuery({
    queryKey: ['universe', 'materials'],
    queryFn: fetchMaterialsList,
  })
}
