import { EquityCurve } from "../components/charts/EquityCurve";
import { TrendLines } from "../components/charts/TrendLines";

/**
 * The numbers behind the story: how confidence in each metal shifted over time,
 * and what following every pick would actually have been worth. Forecast and
 * Backtest stay narrative and quarter-by-quarter; this page is the whole run.
 */
export function Statistics() {
  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Under the hood</div>
        <h1>The numbers behind the picks</h1>
        <p className="page-desc">
          How our confidence in each metal moved, and what the picks were worth end to end.
        </p>
      </div>

      <div className="card">
        <p className="card-title">How the scores moved</p>
        <p className="card-sub">
          Each metal, quarter by quarter. Above the line = we expected it to beat the others.
        </p>
        <TrendLines />
      </div>

      <div className="card section-gap">
        <p className="card-title">All the quarters together</p>
        <p className="card-sub">
          What $100 would have become, following every pick — against the market, all six metals, and
          random guessing.
        </p>
        <EquityCurve />
        <p className="footnote" style={{ marginTop: 14 }}>
          Real dividend-adjusted prices, trading costs included. Every pick used only filings public
          before its quarter began.
        </p>
      </div>
    </div>
  );
}
