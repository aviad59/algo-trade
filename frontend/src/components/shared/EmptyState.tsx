import { Inbox } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

type EmptyStateProps = {
  title?: string
  description?: string
}

export function EmptyState({
  title = 'Pipeline not run',
  description = 'No forecast data is available yet. Run the pipeline to populate rankings and timing signals.',
}: EmptyStateProps) {
  return (
    <Card className="max-w-lg">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Inbox className="size-5 text-muted-foreground" />
          <CardTitle>{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent />
    </Card>
  )
}
