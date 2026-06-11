import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'

type ShowResultsButtonProps = {
  onClick: () => void
  disabled?: boolean
}

export function ShowResultsButton({ onClick, disabled }: ShowResultsButtonProps) {
  return (
    <Button type="button" onClick={onClick} disabled={disabled}>
      <Search className="size-4" />
      Show results
    </Button>
  )
}
