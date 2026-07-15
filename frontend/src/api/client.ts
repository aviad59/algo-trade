import type { ZodType } from 'zod'
import { API_BASE, DATA_SOURCE, DEMO_TOKEN, MOCK_BASE, MOCK_FALLBACK } from './config'
import { markMockFallbackUsed, type MockFallbackReason } from './fallback'

export class ApiError extends Error {
  readonly status: number
  readonly path: string
  readonly code: string | null

  constructor(message: string, status: number, path: string, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.path = path
    this.code = code
  }
}

type ApiErrorBody = {
  error?: string
  message?: string
  detail?: string | { error?: string; message?: string }
}

function userMessageForStatus(status: number): string {
  if (status === 503) {
    return 'The pipeline database is not ready. Run algo-trade-extract or switch to mock mode.'
  }
  if (status >= 500) {
    return 'The API server returned an error.'
  }
  if (status === 404) {
    return 'The requested resource was not found.'
  }
  return 'The request could not be completed.'
}

async function parseErrorBody(response: Response): Promise<{ message: string; code: string | null }> {
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.message === 'string' && body.message.trim()) {
      return { message: body.message, code: body.error ?? null }
    }
    if (typeof body.detail === 'string' && body.detail.trim()) {
      return { message: body.detail, code: null }
    }
    if (body.detail && typeof body.detail === 'object' && typeof body.detail.message === 'string') {
      return { message: body.detail.message, code: body.detail.error ?? null }
    }
  } catch {
    // Response body was not JSON — use status-based message below.
  }
  return { message: userMessageForStatus(response.status), code: null }
}

function fallbackReason(error: unknown): MockFallbackReason {
  if (error instanceof ApiError) {
    if (error.code === 'buffer_unavailable' || error.status === 503) {
      return 'buffer_unavailable'
    }
    if (error.status === 0) {
      return 'network'
    }
  }
  return 'server_error'
}

function fallbackMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Could not reach the live API. Showing demo data instead.'
}

async function fetchAndParse<T>(base: string, path: string, schema: ZodType<T>): Promise<T> {
  const url = `${base}${path}`
  let response: Response
  try {
    response = await fetch(
      url,
      DEMO_TOKEN && base === API_BASE ? { headers: { 'X-Demo-Token': DEMO_TOKEN } } : undefined,
    )
  } catch {
    throw new ApiError(
      'Could not reach the API server. Make sure algo-trade-api is running.',
      0,
      path,
    )
  }

  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, path, code)
  }

  const data: unknown = await response.json()
  return schema.parse(data)
}

/** Fetch from the static mock bundle (`/mock/v1`). */
export async function getMockJson<T>(path: string, schema: ZodType<T>): Promise<T> {
  return fetchAndParse(MOCK_BASE, path, schema)
}

/** POST JSON to the live API (no mock fallback — mutations are api-mode only). */
export async function postJson<T>(path: string, body: unknown, schema: ZodType<T>): Promise<T> {
  const url = `${API_BASE}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(DEMO_TOKEN ? { 'X-Demo-Token': DEMO_TOKEN } : {}),
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError(
      'Could not reach the API server. Make sure algo-trade-api is running.',
      0,
      path,
    )
  }
  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, path, code)
  }
  const data: unknown = await response.json()
  return schema.parse(data)
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
    const message = fallbackMessage(error)
    markMockFallbackUsed({ reason: fallbackReason(error), message })
    if (import.meta.env.DEV) {
      console.warn('[FilingSignal] Live API unavailable — using demo data.')
    }
    return fetchAndParse(MOCK_BASE, mockPath, schema)
  }
}
