import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

type SecFilingLinkProps = {
  url: string
  label?: string
}

export function SecFilingLink({ url, label = 'View on SEC EDGAR' }: SecFilingLinkProps) {
  return (
    <Button variant="outline" asChild>
      <a href={url} target="_blank" rel="noopener noreferrer">
        {label}
        <ExternalLink className="size-4" />
      </a>
    </Button>
  )
}
