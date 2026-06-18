import type { ZodType } from 'zod'
import { API_BASE, DATA_SOURCE, MOCK_BASE, MOCK_FALLBACK } from './config'
import { markMockFallbackUsed } from './fallback'

export class ApiError extends Error {
  readonly status: number
  readonly path: string

  constructor(message: string, status: number, path: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.path = path
  }
}

async function fetchAndParse<T>(base: string, path: string, schema: ZodType<T>): Promise<T> {
  const url = `${base}${path}`
  let response: Response
  try {
    response = await fetch(url)
  } catch (cause) {
    throw new ApiError(
      cause instanceof Error ? cause.message : 'Network error',
      0,
      path,
    )
  }

  if (!response.ok) {
    throw new ApiError(`Request failed: ${response.statusText}`, response.status, path)
  }

  const data: unknown = await response.json()
  return schema.parse(data)
}

/** Fetch from the static mock bundle (`/mock/v1`). */
export async function getMockJson<T>(path: string, schema: ZodType<T>): Promise<T> {
  return fetchAndParse(MOCK_BASE, path, schema)
}

/**
 * Fetch JSON from the configured API base.
 * In `api` mode with `VITE_MOCK_FALLBACK=true`, retries against mock JSON on failure.
 */
export async function getJson<T>(
  path: string,
  schema: ZodType<T>,
  options?: { mockPath?: string },
): Promise<T> {
  try {
    return await fetchAndParse(API_BASE, path, schema)
  } catch (error) {
    const mockPath = options?.mockPath
    if (DATA_SOURCE !== 'api' || !MOCK_FALLBACK || !mockPath) {
      throw error
    }
    markMockFallbackUsed()
    console.warn(`[FilingSignal] API unavailable for ${path}; using mock ${mockPath}`)
    return fetchAndParse(MOCK_BASE, mockPath, schema)
  }
}
