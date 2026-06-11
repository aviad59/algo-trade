import type { Extraction, ExtractionList } from '../types/contract'

export type ExtractionFilters = {
  ticker?: string[]
  material?: string
  from?: string
  to?: string
  limit?: number
  offset?: number
}

export function filterExtractions(
  all: Extraction[],
  filters: ExtractionFilters,
): ExtractionList {
  let items = [...all]

  if (filters.ticker?.length) {
    const set = new Set(filters.ticker.map((t) => t.toUpperCase()))
    items = items.filter((row) => set.has(row.ticker.toUpperCase()))
  }

  if (filters.from) {
    items = items.filter((row) => row.filing_date >= filters.from!)
  }

  if (filters.to) {
    items = items.filter((row) => row.filing_date <= filters.to!)
  }

  if (filters.material) {
    items = items.filter((row) =>
      row.dated_effects.some((effect) => effect.sector === filters.material),
    )
  }

  const offset = filters.offset ?? 0
  const limit = filters.limit ?? 50
  const page = items.slice(offset, offset + limit)

  return {
    contract_version: '1.0',
    total: items.length,
    limit,
    offset,
    items: page,
  }
}
