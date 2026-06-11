import { useParams } from 'react-router-dom'

export function FilingPage() {
  const { extractionId } = useParams<{ extractionId: string }>()

  return (
    <div>
      <h1 className="text-2xl font-bold">Filing {extractionId}</h1>
      <p className="mt-2 text-slate-600">
        Extraction audit trail and SEC link — coming in Phase 5.
      </p>
    </div>
  )
}
