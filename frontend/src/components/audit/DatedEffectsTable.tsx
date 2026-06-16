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
import type { DatedEffect } from '@/types/contract'

type DatedEffectsTableProps = {
  effects: DatedEffect[]
  materialNames?: Record<string, string>
}

export function DatedEffectsTable({ effects, materialNames = {} }: DatedEffectsTableProps) {
  if (effects.length === 0) {
    return (
      <section>
        <h2 className="mb-3 text-lg font-semibold">Dated effects</h2>
        <p className="text-sm text-muted-foreground">No material effects extracted from this filing.</p>
      </section>
    )
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Dated effects</h2>
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Material</TableHead>
              <TableHead>Direction</TableHead>
              <TableHead>Magnitude</TableHead>
              <TableHead>Window</TableHead>
              <TableHead>Rationale</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {effects.map((effect, index) => (
              <TableRow key={`${effect.sector}-${effect.window_start}-${index}`}>
                <TableCell>
                  <Badge variant="outline" asChild>
                    <Link to={`/materials/${effect.sector}`}>
                      {materialNames[effect.sector] ?? effect.sector}
                    </Link>
                  </Badge>
                </TableCell>
                <TableCell className="capitalize">{effect.direction}</TableCell>
                <TableCell className="capitalize">{effect.magnitude}</TableCell>
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
