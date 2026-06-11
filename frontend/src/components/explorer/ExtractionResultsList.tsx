import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate, formatPercent } from '@/lib/format'
import type { Extraction } from '@/types/contract'

type ExtractionResultsListProps = {
  extractions: Extraction[]
  materialNames?: Record<string, string>
}

function ExtractionRow({
  extraction,
  materialNames,
}: {
  extraction: Extraction
  materialNames: Record<string, string>
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <TableRow>
        <TableCell>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={() => setExpanded((value) => !value)}
            aria-label={expanded ? 'Collapse effects' : 'Expand effects'}
          >
            {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </Button>
        </TableCell>
        <TableCell>
          <Badge variant="outline" asChild>
            <Link to={`/companies/${extraction.ticker}`}>{extraction.ticker}</Link>
          </Badge>
        </TableCell>
        <TableCell>
          <Link
            to={`/filings/${extraction.id}`}
            className="font-medium text-primary hover:underline"
          >
            {extraction.filing_type}
          </Link>
        </TableCell>
        <TableCell>{formatDate(extraction.filing_date)}</TableCell>
        <TableCell>{extraction.dated_effects.length}</TableCell>
        <TableCell className="text-muted-foreground">
          {formatPercent(extraction.extractor_confidence)}
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow>
          <TableCell colSpan={6} className="bg-muted/30">
            <div className="space-y-2 py-2">
              {extraction.dated_effects.map((effect, index) => (
                <div
                  key={`${effect.sector}-${effect.window_start}-${index}`}
                  className="flex flex-wrap items-start gap-2 text-sm"
                >
                  <Badge variant="outline" asChild>
                    <Link to={`/materials/${effect.sector}`}>
                      {materialNames[effect.sector] ?? effect.sector}
                    </Link>
                  </Badge>
                  <span className="capitalize text-muted-foreground">
                    {effect.direction} · {effect.magnitude}
                  </span>
                  <span className="text-muted-foreground">
                    {formatDate(effect.window_start)} – {formatDate(effect.window_end)}
                  </span>
                  <span>{effect.rationale}</span>
                </div>
              ))}
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  )
}

export function ExtractionResultsList({
  extractions,
  materialNames = {},
}: ExtractionResultsListProps) {
  const sorted = [...extractions].sort((a, b) => b.filing_date.localeCompare(a.filing_date))

  return (
    <div className="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10" />
            <TableHead>Ticker</TableHead>
            <TableHead>Filing</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Effects</TableHead>
            <TableHead>Confidence</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((extraction) => (
            <ExtractionRow
              key={extraction.id}
              extraction={extraction}
              materialNames={materialNames}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
