import { FileText } from 'lucide-react'

type SourceSpanHighlightProps = {
  sourceSpan: string
}

export function SourceSpanHighlight({ sourceSpan }: SourceSpanHighlightProps) {
  return (
    <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-3">
      <div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-amber-200/90">
        <FileText className="size-3.5" />
        Source span
      </div>
      <p className="font-mono text-sm text-amber-50/90">{sourceSpan}</p>
    </div>
  )
}
