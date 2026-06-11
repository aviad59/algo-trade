import { useParams } from 'react-router-dom'

export function CompanyPage() {
  const { ticker } = useParams<{ ticker: string }>()

  return (
    <div>
      <h1 className="text-2xl font-bold">{ticker}</h1>
      <p className="mt-2 text-slate-600">
        Company filings and extractions — coming in Phase 5.
      </p>
    </div>
  )
}
