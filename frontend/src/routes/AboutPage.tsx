import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { APP_NAME, APP_TAGLINE } from '@/lib/brand'

export function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">About {APP_NAME}</h1>
        <p className="mt-2 text-muted-foreground">{APP_TAGLINE}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>What this tool does</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            {APP_NAME} reads U.S. SEC EDGAR filings, extracts each company&apos;s forward-looking
            material dependencies, and surfaces narrative-derived demand signals over time.
          </p>
          <p>
            The forecast dashboard ranks materials, charts filing-derived timing signals, and
            supports a full audit trail from material → company → filing → source span.
          </p>
        </CardContent>
      </Card>

      <Alert>
        <AlertTitle>Disclaimer</AlertTitle>
        <AlertDescription>
          This project is for research and educational purposes only. Nothing produced by this tool
          is financial advice. LLMs hallucinate, filings can be misread, and markets do not care what
          a model thinks. Do your own due diligence.
        </AlertDescription>
      </Alert>

      <p className="text-sm text-muted-foreground">
        Pipeline design and architecture are documented in the{' '}
        <a
          href="https://github.com/aviad59/algo-trade"
          className="text-primary underline underline-offset-4"
          target="_blank"
          rel="noreferrer"
        >
          project repository
        </a>
        .
      </p>
    </div>
  )
}
