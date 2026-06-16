import { useQuery } from '@tanstack/react-query'
import { fetchManufacturersList } from '../api/endpoints'

export function useManufacturers() {
  return useQuery({
    queryKey: ['universe', 'manufacturers'],
    queryFn: fetchManufacturersList,
  })
}
