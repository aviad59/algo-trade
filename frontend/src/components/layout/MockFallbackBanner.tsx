import { useEffect, useState } from 'react'
import {
  getMockFallbackInfo,
  isMockFallbackActive,
  subscribeMockFallback,
} from '@/api/fallback'
import { DATA_SOURCE } from '@/api/config'

const DEFAULT_MESSAGE =
  'Live API unavailable — showing demo data from the static mock bundle.'

export function MockFallbackBanner() {
  const [active, setActive] = useState(isMockFallbackActive())
  const [message, setMessage] = useState(getMockFallbackInfo()?.message ?? DEFAULT_MESSAGE)

  useEffect(() => {
    return subscribeMockFallback(() => {
      setActive(true)
      setMessage(getMockFallbackInfo()?.message ?? DEFAULT_MESSAGE)
    })
  }, [])

  if (DATA_SOURCE !== 'api' || !active) {
    return null
  }

  return (
    <div
      className="border-b border-amber-500/25 bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-50/95"
      role="status"
    >
      <p>{message}</p>
      <p className="mt-1 text-xs text-amber-100/70">
        To use live pipeline data, run <code className="rounded bg-black/20 px-1">algo-trade-api</code>{' '}
        and populate the buffer with <code className="rounded bg-black/20 px-1">algo-trade-extract</code>
        , or set <code className="rounded bg-black/20 px-1">VITE_DATA_SOURCE=mock</code> in{' '}
        <code className="rounded bg-black/20 px-1">.env</code>.
      </p>
    </div>
  )
}
