import { describe, expect, it } from 'vitest'
import {
  parseExplorerSearch,
  serializeExplorerParams,
  validateExplorerParams,
} from '../src/lib/explorerParams'

describe('explorerParams', () => {
  it('parses and serializes explorer URL params', () => {
    const parsed = parseExplorerSearch('tickers=TSLA,GM&from=2026-01-01&to=2026-06-30&material=lithium')
    expect(parsed).toEqual({
      tickers: ['TSLA', 'GM'],
      from: '2026-01-01',
      to: '2026-06-30',
      material: 'lithium',
    })

    const serialized = serializeExplorerParams(parsed)
    expect(parseExplorerSearch(serialized)).toEqual(parsed)
  })

  it('validates ticker and date range requirements', () => {
    expect(validateExplorerParams({ tickers: [] }).valid).toBe(false)
    expect(
      validateExplorerParams({
        tickers: ['TSLA'],
        from: '2026-06-30',
        to: '2026-01-01',
      }).valid,
    ).toBe(false)
    expect(
      validateExplorerParams({
        tickers: ['TSLA'],
        from: '2026-01-01',
        to: '2026-06-30',
      }).valid,
    ).toBe(true)
  })
})
