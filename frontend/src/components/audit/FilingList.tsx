import { Link } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate } from '@/lib/format'
import type { Extraction } from '@/types/contract'

type FilingListProps = {
  extractions: Extraction[]
}

export function FilingList({ extractions }: FilingListProps) {
  const sorted = [...extractions].sort((a, b) => b.filing_date.localeCompare(a.filing_date))

  if (sorted.length === 0) {
    return (
      <section>
        <h2 className="mb-3 text-lg font-semibold">Filings</h2>
        <p className="text-sm text-muted-foreground">No extractions found for this company.</p>
      </section>
    )
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Filings</h2>
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filing</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Effects</TableHead>
              <TableHead>Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((extraction) => (
              <TableRow key={extraction.id}>
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
                  {Math.round(extraction.extractor_confidence * 100)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}
