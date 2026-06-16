import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'

type CompanyInfo = {
  ticker: string
  cik: string
  name: string
  gics_sector: string
  gics_sub_industry?: string
}

type CompanyHeaderProps = {
  company: CompanyInfo
}

export function CompanyHeader({ company }: CompanyHeaderProps) {
  return (
    <header className="space-y-3">
      <p className="text-sm text-muted-foreground">
        <Link to="/" className="hover:text-foreground">
          Forecast
        </Link>{' '}
        / {company.ticker}
      </p>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{company.name}</h1>
          <p className="mt-1 text-muted-foreground">
            {company.ticker} · CIK {company.cik}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{company.gics_sector}</Badge>
          {company.gics_sub_industry ? (
            <Badge variant="secondary">{company.gics_sub_industry}</Badge>
          ) : null}
        </div>
      </div>
    </header>
  )
}
