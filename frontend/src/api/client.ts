import type { ZodType } from 'zod'
import { API_BASE } from './config'

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

export async function getJson<T>(path: string, schema: ZodType<T>): Promise<T> {
  const url = `${API_BASE}${path}`
  const response = await fetch(url)

  if (!response.ok) {
    throw new ApiError(`Request failed: ${response.statusText}`, response.status, path)
  }

  const data: unknown = await response.json()
  return schema.parse(data)
}
