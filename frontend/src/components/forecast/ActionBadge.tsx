import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ForecastAction } from '@/types/contract'

type ActionBadgeProps = {
  action: ForecastAction | null
  className?: string
}

export function ActionBadge({ action, className }: ActionBadgeProps) {
  if (!action) {
    return (
      <Badge variant="secondary" className={className}>
        —
      </Badge>
    )
  }

  if (action === 'BUY') {
    return (
      <Badge
        variant="outline"
        className={cn('border-emerald-500/40 bg-emerald-500/15 text-emerald-300', className)}
      >
        BUY
      </Badge>
    )
  }

  return (
    <Badge variant="destructive" className={className}>
      SELL
    </Badge>
  )
}
