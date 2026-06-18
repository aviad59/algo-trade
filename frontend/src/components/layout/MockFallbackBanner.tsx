import { useEffect, useState } from 'react'
import { isMockFallbackActive, subscribeMockFallback } from '@/api/fallback'
import { DATA_SOURCE } from '@/api/config'

export function MockFallbackBanner() {
  const [active, setActive] = useState(isMockFallbackActive())

  useEffect(() => {
    return subscribeMockFallback(() => setActive(true))
  }, [])

  if (DATA_SOURCE !== 'api' || !active) {
    return null
  }

  return (
    <div
      className="border-b border-sky-500/20 bg-sky-500/10 px-4 py-2 text-center text-sm text-sky-100/90"
      role="status"
    >
      Live API unavailable — showing demo data from the static mock bundle.
    </div>
  )
}
