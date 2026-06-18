export const API_BASE = import.meta.env.VITE_API_BASE ?? '/mock/v1'
export const DATA_SOURCE = (import.meta.env.VITE_DATA_SOURCE ?? 'mock') as 'mock' | 'api'
export const MOCK_BASE = '/mock/v1'

/** When `DATA_SOURCE=api`, retry failed requests against static mock JSON. */
export const MOCK_FALLBACK =
  DATA_SOURCE === 'api' && (import.meta.env.VITE_MOCK_FALLBACK ?? 'true') !== 'false'
