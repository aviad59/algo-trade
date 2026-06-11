export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}

export function formatSignal(signal: number): string {
  return signal.toFixed(2)
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function formatMonth(isoMonth: string): string {
  const [year, month] = isoMonth.split('-')
  const date = new Date(Number(year), Number(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}
