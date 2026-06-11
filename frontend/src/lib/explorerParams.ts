export type ExplorerParams = {
  tickers: string[]
  from?: string
  to?: string
  material?: string
}

export function parseExplorerSearch(search: string): ExplorerParams {
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)

  const tickers = (params.get('tickers') ?? '')
    .split(',')
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean)

  const from = params.get('from') ?? undefined
  const to = params.get('to') ?? undefined
  const material = params.get('material') ?? undefined

  return { tickers, from, to, material }
}

export function serializeExplorerParams(filters: ExplorerParams): string {
  const params = new URLSearchParams()

  if (filters.tickers.length > 0) {
    params.set('tickers', filters.tickers.join(','))
  }
  if (filters.from) {
    params.set('from', filters.from)
  }
  if (filters.to) {
    params.set('to', filters.to)
  }
  if (filters.material) {
    params.set('material', filters.material)
  }

  const query = params.toString()
  return query ? `?${query}` : ''
}

export function validateExplorerParams(filters: ExplorerParams): {
  valid: boolean
  error?: string
} {
  if (filters.tickers.length === 0) {
    return { valid: false, error: 'Select at least one ticker.' }
  }

  if (filters.from && filters.to && filters.from > filters.to) {
    return { valid: false, error: 'Start date must be on or before end date.' }
  }

  return { valid: true }
}

export function toExtractionFilters(filters: ExplorerParams) {
  return {
    ticker: filters.tickers,
    from: filters.from,
    to: filters.to,
    material: filters.material,
  }
}
