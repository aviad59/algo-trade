import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Instruments } from '@/types/contract'

const BUCKET_LABELS: Record<keyof Instruments['buckets'], string> = {
  producers: 'Producers',
  etfs: 'ETFs',
  physical: 'Physical',
  futures: 'Futures',
  transporters: 'Transporters',
  downstream_consumers: 'Downstream consumers',
}

type InstrumentsPanelProps = {
  instruments: Instruments
}

function isTicker(value: string): boolean {
  return /^[A-Z]{1,5}$/.test(value)
}

function InstrumentItem({ value }: { value: string }) {
  if (isTicker(value)) {
    return (
      <Badge variant="outline" asChild>
        <Link to={`/companies/${value}`}>{value}</Link>
      </Badge>
    )
  }

  return <Badge variant="secondary">{value}</Badge>
}

export function InstrumentsPanel({ instruments }: InstrumentsPanelProps) {
  const buckets = Object.entries(instruments.buckets) as Array<
    [keyof Instruments['buckets'], string[]]
  >

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Tradable instruments</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {buckets.map(([key, items]) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{BUCKET_LABELS[key]}</CardTitle>
            </CardHeader>
            <CardContent>
              {items.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {items.map((item) => (
                    <InstrumentItem key={item} value={item} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No mapped instruments</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
