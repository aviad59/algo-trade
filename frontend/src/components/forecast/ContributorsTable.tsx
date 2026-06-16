import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
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

type ContributorsTableProps = {
  extractions: Extraction[]
  materialId: string
}

export function ContributorsTable({ extractions, materialId }: ContributorsTableProps) {
  const rows = extractions.flatMap((extraction) =>
    extraction.dated_effects
      .filter((effect) => effect.sector === materialId)
      .map((effect) => ({
        extraction,
        effect,
      })),
  )

  if (rows.length === 0) {
    return (
      <section>
        <h2 className="mb-3 text-lg font-semibold">Contributing filings</h2>
        <p className="text-sm text-muted-foreground">No extractions reference this material yet.</p>
      </section>
    )
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Contributing filings</h2>
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Filing</TableHead>
              <TableHead>Effect</TableHead>
              <TableHead>Window</TableHead>
              <TableHead>Rationale</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ extraction, effect }) => (
              <TableRow key={`${extraction.id}-${effect.window_start}`}>
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
                    {extraction.filing_type} · {formatDate(extraction.filing_date)}
                  </Link>
                </TableCell>
                <TableCell className="capitalize">
                  {effect.direction} · {effect.magnitude}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(effect.window_start)} – {formatDate(effect.window_end)}
                </TableCell>
                <TableCell className="max-w-md whitespace-normal text-muted-foreground">
                  {effect.rationale}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}
