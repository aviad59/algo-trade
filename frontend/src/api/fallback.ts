/** Tracks whether any request fell back to static mock data this session. */

export type MockFallbackReason = 'network' | 'server_error' | 'buffer_unavailable'

export type MockFallbackInfo = {
  reason: MockFallbackReason
  message: string
}

let info: MockFallbackInfo | null = null
const listeners = new Set<() => void>()

export function getMockFallbackInfo(): MockFallbackInfo | null {
  return info
}

export function isMockFallbackActive(): boolean {
  return info !== null
}

export function markMockFallbackUsed(next: MockFallbackInfo): void {
  if (!info) {
    info = next
  }
  for (const listener of listeners) {
    listener()
  }
}

export function subscribeMockFallback(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Test helper — reset session state between tests. */
export function resetMockFallbackState(): void {
  info = null
}
