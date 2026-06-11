export function AboutPage() {
  return (
    <div className="prose prose-slate max-w-none">
      <h1 className="text-2xl font-bold">About algo-trade</h1>
      <p className="mt-4 text-slate-700">
        algo-trade is an agentic pipeline that reads U.S. SEC EDGAR filings, extracts
        each company&apos;s forward-looking material dependencies, and surfaces
        narrative-derived demand signals over time.
      </p>
      <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-950">
        <h2 className="text-lg font-semibold">Disclaimer</h2>
        <p className="mt-2 text-sm">
          This project is for research and educational purposes only. Nothing produced by
          this tool is financial advice. LLMs hallucinate, filings can be misread, and
          markets do not care what a model thinks. Do your own due diligence.
        </p>
      </div>
      <p className="mt-6 text-sm text-slate-600">
        Pipeline design and architecture are documented in the{' '}
        <a
          href="https://github.com/aviad59/algo-trade"
          className="text-blue-600 underline"
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
