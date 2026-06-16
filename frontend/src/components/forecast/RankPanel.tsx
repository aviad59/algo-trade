import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatScore } from '@/lib/format'
import type { RankedMaterial } from '@/types/contract'

type RankPanelProps = {
  entry: RankedMaterial
  rank: number
}

export function RankPanel({ entry, rank }: RankPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ranking context</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-semibold">#{rank}</span>
          <span className="text-muted-foreground">Score {formatScore(entry.score)}</span>
        </div>
        <p>{entry.rationale}</p>
        <div>
          <p className="mb-2 font-medium">Supporting tickers</p>
          <div className="flex flex-wrap gap-1">
            {entry.supporting_tickers.map((ticker) => (
              <Badge key={ticker} variant="outline" asChild>
                <Link to={`/companies/${ticker}`}>{ticker}</Link>
              </Badge>
            ))}
          </div>
        </div>
        {entry.dissenting_evidence.length > 0 ? (
          <div>
            <p className="mb-2 font-medium">Dissenting evidence</p>
            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
              {entry.dissenting_evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
