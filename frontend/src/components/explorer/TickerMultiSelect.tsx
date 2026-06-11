import { useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

type Manufacturer = {
  ticker: string
  name: string
}

type TickerMultiSelectProps = {
  manufacturers: Manufacturer[]
  selected: string[]
  onChange: (tickers: string[]) => void
}

export function TickerMultiSelect({ manufacturers, selected, onChange }: TickerMultiSelectProps) {
  const [query, setQuery] = useState('')

  const suggestions = useMemo(() => {
    const normalized = query.trim().toUpperCase()
    if (!normalized) {
      return manufacturers.filter((item) => !selected.includes(item.ticker))
    }

    return manufacturers.filter((item) => {
      if (selected.includes(item.ticker)) {
        return false
      }
      return (
        item.ticker.includes(normalized) ||
        item.name.toUpperCase().includes(normalized)
      )
    })
  }, [manufacturers, query, selected])

  const addTicker = (ticker: string) => {
    if (!selected.includes(ticker)) {
      onChange([...selected, ticker])
    }
    setQuery('')
  }

  const removeTicker = (ticker: string) => {
    onChange(selected.filter((item) => item !== ticker))
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium" htmlFor="ticker-search">
        Tickers
      </label>
      <div className="flex flex-wrap gap-1">
        {selected.map((ticker) => (
          <Badge key={ticker} variant="secondary" className="gap-1 pr-1">
            {ticker}
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="size-4"
              onClick={() => removeTicker(ticker)}
              aria-label={`Remove ${ticker}`}
            >
              <X className="size-3" />
            </Button>
          </Badge>
        ))}
      </div>
      <input
        id="ticker-search"
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && suggestions[0]) {
            event.preventDefault()
            addTicker(suggestions[0].ticker)
          }
        }}
        placeholder="Search ticker or company name"
        className="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        list="ticker-suggestions"
      />
      {query && suggestions.length > 0 ? (
        <ul className="max-h-40 overflow-y-auto rounded-lg border bg-card text-sm shadow-sm">
          {suggestions.slice(0, 8).map((item) => (
            <li key={item.ticker}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted"
                onClick={() => addTicker(item.ticker)}
              >
                <span className="font-medium">{item.ticker}</span>
                <span className="text-muted-foreground">{item.name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
