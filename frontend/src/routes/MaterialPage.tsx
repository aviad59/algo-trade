import { useParams } from 'react-router-dom'

export function MaterialPage() {
  const { materialId } = useParams<{ materialId: string }>()

  return (
    <div>
      <h1 className="text-2xl font-bold capitalize">{materialId}</h1>
      <p className="mt-2 text-slate-600">
        Material forecast chart and contributors — coming in Phase 4.
      </p>
    </div>
  )
}
