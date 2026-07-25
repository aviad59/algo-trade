import { PipelineExplorer } from "../components/PipelineExplorer";

export function Home() {
  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">LLM research pipeline · materials sector rotation</div>
        <h1>Turn SEC filings into an auditable, point-in-time materials forecast.</h1>
        <p className="page-desc">
          FilingSignal is an investment-research platform. It reads SEC filings, scores six industrial materials
          each quarter, and answers one question: <em>if you buy exactly one material's miner ETF, which one?</em>{" "}
          Then it honestly checks whether that pick actually worked.
        </p>
      </div>

      <div className="section-gap">
        <PipelineExplorer />
      </div>
    </div>
  );
}
