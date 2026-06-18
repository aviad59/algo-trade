import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { forecastSummarySchema } from '../src/types/contract'
import { getJson } from '../src/api/client'
import {
  getMockFallbackInfo,
  isMockFallbackActive,
  resetMockFallbackState,
} from '../src/api/fallback'

vi.mock('../src/api/config', () => ({
  API_BASE: '/api/v1',
  DATA_SOURCE: 'api',
  MOCK_BASE: '/mock/v1',
  MOCK_FALLBACK: true,
}))

const mockSummary = {
  contract_version: '1.0' as const,
  as_of: '2026-06-08',
  pipeline_run_at: '2026-06-08T12:00:00Z',
  universe_count: 10,
  extractions_count: 3,
  top_materials: [],
}

describe('API mock fallback', () => {
  beforeEach(() => {
    resetMockFallbackState()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses mock JSON when the live API fails', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockSummary), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

    const result = await getJson('/forecast/summary', forecastSummarySchema, {
      mockPath: '/forecast/summary.json',
    })

    expect(result.as_of).toBe('2026-06-08')
    expect(isMockFallbackActive()).toBe(true)
    expect(getMockFallbackInfo()?.reason).toBe('network')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/forecast/summary')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/mock/v1/forecast/summary.json')
  })

  it('surfaces user-safe API error messages on 500', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: 'internal_error',
            message: 'The server encountered an unexpected error. Please try again later.',
          }),
          { status: 500, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockSummary), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

    await getJson('/forecast/summary', forecastSummarySchema, {
      mockPath: '/forecast/summary.json',
    })

    expect(getMockFallbackInfo()?.message).toContain('unexpected error')
    expect(getMockFallbackInfo()?.reason).toBe('server_error')
  })

  it('rethrows when mock path is not provided', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(
      getJson('/forecast/summary', forecastSummarySchema),
    ).rejects.toThrow('Could not reach the API server')
    expect(isMockFallbackActive()).toBe(false)
  })
})
