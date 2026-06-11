import { Link, useNavigate } from 'react-router-dom'
import { ActionBadge } from '@/components/forecast/ActionBadge'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatScore } from '@/lib/format'
import type { ForecastRanking, ForecastSummary } from '@/types/contract'

type MaterialRankingTableProps = {
  ranking: ForecastRanking
  summary: ForecastSummary
}

export function MaterialRankingTable({ ranking, summary }: MaterialRankingTableProps) {
  const navigate = useNavigate()

  const actionByMaterial = new Map(
    summary.top_materials.map((material) => [material.material_id, material.latest_action]),
  )

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Material ranking</h2>
      <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>Material</TableHead>
              <TableHead>Score</TableHead>
              <TableHead>Signal</TableHead>
              <TableHead>Supporting tickers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ranking.ranked_materials.map((material, index) => (
              <TableRow
                key={material.material_id}
                className="cursor-pointer"
                onClick={() => navigate(`/materials/${material.material_id}`)}
              >
                <TableCell className="font-medium text-muted-foreground">{index + 1}</TableCell>
                <TableCell className="font-medium">{material.name}</TableCell>
                <TableCell>{formatScore(material.score)}</TableCell>
                <TableCell>
                  <ActionBadge action={actionByMaterial.get(material.material_id) ?? null} />
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {material.supporting_tickers.map((ticker) => (
                      <Badge key={ticker} variant="outline" asChild>
                        <Link
                          to={`/companies/${ticker}`}
                          onClick={(event) => event.stopPropagation()}
                        >
                          {ticker}
                        </Link>
                      </Badge>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}
