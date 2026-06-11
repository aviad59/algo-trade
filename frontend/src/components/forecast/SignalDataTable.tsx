import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatMonth, formatSignal } from '@/lib/format'
import type { ForecastCurvePoint } from '@/types/contract'

type SignalDataTableProps = {
  curve: ForecastCurvePoint[]
}

export function SignalDataTable({ curve }: SignalDataTableProps) {
  const [open, setOpen] = useState(false)

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Chart data</h2>
        <Button variant="outline" size="sm" onClick={() => setOpen((value) => !value)}>
          {open ? 'Hide table' : 'View as table'}
        </Button>
      </div>
      {open ? (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Month</TableHead>
                <TableHead>Signal</TableHead>
                <TableHead>Forward AUC</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {curve.map((point) => (
                <TableRow key={point.month}>
                  <TableCell>{formatMonth(point.month)}</TableCell>
                  <TableCell>{formatSignal(point.signal)}</TableCell>
                  <TableCell>{formatSignal(point.forward_AUC)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </section>
  )
}
