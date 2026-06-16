import { AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatPercent } from '@/lib/format'
import type { Extraction } from '@/types/contract'

type ExtractionCardProps = {
  extraction: Extraction
  companyName?: string
}

export function ExtractionCard({ extraction, companyName }: ExtractionCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {companyName ?? extraction.ticker} · {extraction.filing_type}
        </CardTitle>
        <CardDescription>
          Filed {formatDate(extraction.filing_date)} · Extraction {extraction.id}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <p className="text-muted-foreground">Extractor confidence</p>
          <p className="text-lg font-semibold">{formatPercent(extraction.extractor_confidence)}</p>
        </div>
        {extraction.flagged_risks.length > 0 ? (
          <div>
            <p className="mb-2 flex items-center gap-2 font-medium">
              <AlertTriangle className="size-4 text-amber-600" />
              Flagged risks
            </p>
            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
              {extraction.flagged_risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
