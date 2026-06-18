/** Tracks whether any request fell back to static mock data this session. */

let active = false
const listeners = new Set<() => void>()

export function isMockFallbackActive(): boolean {
  return active
}

export function markMockFallbackUsed(): void {
  if (active) return
  active = true
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
  active = false
}
