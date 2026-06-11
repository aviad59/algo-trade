import { useQuery } from '@tanstack/react-query'
import { fetchMaterialForecast } from '../api/endpoints'

export function useMaterialForecast(materialId: string) {
  return useQuery({
    queryKey: ['forecast', 'materials', materialId],
    queryFn: () => fetchMaterialForecast(materialId),
    enabled: Boolean(materialId),
  })
}
