import { PipelineExplorer } from "../components/PipelineExplorer";
import { AiMark } from "../components/ui";
import type { Page } from "../lib/useHashRoute";

export function Home({ navigate }: { navigate: (p: Page) => void }) {
  return (
    <div className="page">
      <div className="page-head rise">
        <div className="eyebrow">FilingSignal</div>
        <h1 className="claim">
          Can an AI read SEC filings and pick next quarter's best mining ETF?
        </h1>
        <p className="page-desc claim-sub">
          Every quarter it ranks six metals — copper, gold, uranium, silver, steel, rare earths —
          from what mining companies told the SEC, buys the top one's miner fund on paper,
          and then checks honestly whether that worked.
        </p>
      </div>

      <div className="grid g3 rise d1">
        <button className="link-card" onClick={() => navigate("forecast")}>
          <span>
            <span className="link-card-title">See this quarter's pick</span>
            <span className="link-card-sub">Which metal it chose, and the filings behind it.</span>
          </span>
          <span className="link-card-arrow" aria-hidden="true">→</span>
        </button>
        <button className="link-card" onClick={() => navigate("backtest")}>
          <span>
            <span className="link-card-title">Did it actually work?</span>
            <span className="link-card-sub">Every past pick against the market, quarter by quarter.</span>
          </span>
          <span className="link-card-arrow" aria-hidden="true">→</span>
        </button>
        <button className="link-card" onClick={() => navigate("filings")}>
          <span>
            <span className="link-card-title"><AiMark size={14} /> Try it yourself</span>
            <span className="link-card-sub">Watch our AI read a real SEC filing, live.</span>
          </span>
          <span className="link-card-arrow" aria-hidden="true">→</span>
        </button>
      </div>

      <div className="section-gap rise d2">
        <PipelineExplorer />
      </div>
    </div>
  );
}
