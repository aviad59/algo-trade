export const API_BASE = import.meta.env.VITE_API_BASE ?? '/mock/v1'
export const DATA_SOURCE = (import.meta.env.VITE_DATA_SOURCE ?? 'mock') as 'mock' | 'api'
export const MOCK_BASE = '/mock/v1'

/** When `DATA_SOURCE=api`, retry failed requests against static mock JSON. */
export const MOCK_FALLBACK =
  DATA_SOURCE === 'api' && (import.meta.env.VITE_MOCK_FALLBACK ?? 'true') !== 'false'

const DEMO_TOKEN_STORAGE_KEY = 'filingsignal-demo-token'

/**
 * Demo access token for live Agent #2 ranking. Arrives once via
 * `?demo=SECRET` in the URL (e.g. the link handed to a reviewer), is kept in
 * localStorage, and is scrubbed from the address bar. `?demo=` (empty)
 * clears it.
 */
function resolveDemoToken(): string | null {
  try {
    const url = new URL(window.location.href)
    const fromUrl = url.searchParams.get('demo')
    if (fromUrl !== null) {
      if (fromUrl === '') {
        localStorage.removeItem(DEMO_TOKEN_STORAGE_KEY)
      } else {
        localStorage.setItem(DEMO_TOKEN_STORAGE_KEY, fromUrl)
      }
      url.searchParams.delete('demo')
      window.history.replaceState(null, '', url)
    }
    return localStorage.getItem(DEMO_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export const DEMO_TOKEN = resolveDemoToken()
