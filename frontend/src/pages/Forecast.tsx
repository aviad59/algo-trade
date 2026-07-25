import { ForecastTracker } from "../components/ForecastTracker";
import { ScoreBars } from "../components/charts/ScoreBars";
import { TrendLines } from "../components/charts/TrendLines";
import { FILINGS_DIGESTED, FORECAST_QUARTER, MATERIALS, PICK_RATING, PRIOR_QUARTER, PUBLISHED_DATE } from "../data/fixtures";
import { signed } from "../lib/format";

/** Frozen universe → ETF long names (universe/materials.yaml). */
const ETF_NAMES: Record<string, string> = {
  COPX: "Global X Copper Miners ETF",
  GDX: "VanEck Gold Miners ETF",
  URNM: "Sprott Uranium Miners ETF",
  SIL: "Global X Silver Miners ETF",
  SLX: "VanEck Steel ETF",
  REMX: "VanEck Rare Earth & Strategic Metals ETF",
};

export function Forecast() {
  const pick = MATERIALS[0];
  const margin = MATERIALS.length > 1 ? pick.z - MATERIALS[1].z : 0;
  const confidence = margin >= 0.5 ? "High" : margin >= 0.25 ? "Moderate" : "Low";
  // Agent #2's stored recommendation — only shown if it's actually about this pick
  const rating = PICK_RATING && PICK_RATING.material === pick.material ? PICK_RATING : null;

  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Forecast · published {PUBLISHED_DATE}</div>
        <h1>Latest Forecast — {FORECAST_QUARTER}</h1>
        <p className="page-desc">
          Materials ranked by a point-in-time cross-sectional z-score built from {FILINGS_DIGESTED} filings public
          through {PRIOR_QUARTER}. The top-ranked material maps to its frozen miner-equity ETF.
        </p>
      </div>

      <div className="card hero-card">
        <div className="hero-grid">
          <div>
            <div className="kpi-label">Top pick · {FORECAST_QUARTER}</div>
            <div className="hero-num" style={{ marginTop: 8 }}>{pick.material}</div>
            <div className="hero-etf">
              <span className="tk" style={{ fontSize: 15, color: "var(--accent-ink)" }}>{pick.etf}</span>
              <span style={{ color: "var(--ink-3)", fontSize: 12.5 }}>{ETF_NAMES[pick.etf] ?? ""}</span>
            </div>
            <div className="hero-stats">
              <div><div className="kpi-label">z-score</div><div className="kpi-value mono" style={{ fontSize: 22 }}>{signed(pick.z)}</div></div>
              <div><div className="kpi-label">Rank confidence</div><div className="kpi-value" style={{ fontSize: 22 }}>{confidence}</div></div>
              <div><div className="kpi-label">Margin vs #2</div><div className="kpi-value mono" style={{ fontSize: 22 }}>{signed(margin)}</div></div>
            </div>
          </div>
          <div>
            <div className="kpi-label" style={{ marginBottom: 8 }}>Why {pick.material.toLowerCase()}</div>
            {rating ? (
              <>
                <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-2)" }}>{rating.prose}</p>
                <p className="footnote" style={{ marginTop: 10 }}>
                  Agent #2 · stored for {rating.quarter}{rating.model ? ` · ${rating.model}` : ""} — narrates the deterministic rank, never sets it.
                </p>
              </>
            ) : (
              <p className="footnote" style={{ marginTop: 0 }}>
                No stored recommendation for {FORECAST_QUARTER} yet — run <span className="mono">filingsignal rate</span> to
                have Agent #2 write (and persist) the grounded call for this quarter.
              </p>
            )}
          </div>
        </div>
      </div>

      <ForecastTracker />

      <div className="section-gap split">
        <div className="card">
          <p className="card-title">Material ranking — {FORECAST_QUARTER}</p>
          <p className="card-sub">Producer/consumer sub-scores combine, then standardize cross-sectionally. Gold is producer-only (demand is macro).</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th><th>Material</th><th>ETF</th>
                  <th className="num">z-score</th><th className="num">Producer</th><th className="num">Consumer</th><th className="num">Filings</th>
                </tr>
              </thead>
              <tbody>
                {MATERIALS.map((m) => (
                  <tr key={m.material} className="hoverable-row">
                    <td><span className={`rank-chip${m.rank === 1 ? " top" : ""}`}>{m.rank}</span></td>
                    <td style={{ fontWeight: m.rank === 1 ? 650 : 500 }}>{m.material}</td>
                    <td><span className="tk">{m.etf}</span></td>
                    <td className="num" style={{ fontWeight: 700, color: m.z >= 0 ? "var(--ink)" : "var(--bad-text)" }}>{signed(m.z)}</td>
                    <td className="num">{m.producerScore.toFixed(2)}</td>
                    <td className="num" style={{ color: m.consumerScore === null ? "var(--ink-3)" : undefined }}>{m.consumerScore === null ? "—" : m.consumerScore.toFixed(2)}</td>
                    <td className="num">{m.filings}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <p className="card-title">Scores this quarter</p>
          <p className="card-sub">z-score, diverging from the quarter average. Top pick emphasized.</p>
          <ScoreBars />
        </div>
      </div>

      <div className="card section-gap">
        <p className="card-title">Score trend — last 6 quarters</p>
        <p className="card-sub">Cross-sectional z-score per quarter for the top four materials by current rank.</p>
        <TrendLines />
      </div>

      <div className="section-gap split">
        <div className="card">
          <p className="card-title">Why this forecast?</p>
          <p className="card-sub">The quotes Agent #2 cited in its stored recommendation. It may only cite quotes that exist in the buffer.</p>
          {rating && rating.supporting.length > 0 ? (
            <div>
              {rating.supporting.map((s, i) => (
                <div className="ev-quote" key={`${s.ticker}-${i}`}>
                  “{s.quote.replace(/^[“"]|[”"]$/g, "")}”
                  <span className="src">{s.ticker} · cited by Agent #2</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="footnote">No cited quotes stored for this quarter yet.</p>
          )}
        </div>
        <div className="card" style={{ borderLeft: "3px solid var(--bad)" }}>
          <p className="card-title">Dissent &amp; risks</p>
          <p className="card-sub">What would make this call wrong.</p>
          <span className="ev-tag bear">Bearish · producer</span>
          <div className="ev-quote">
            “We are experiencing softening demand in Chinese construction end-markets and expect volume headwinds to persist through fiscal 2026.”
            <span className="src">SCCO · 10-Q · 2026-06-30 · weight 0.07</span>
          </div>
          <hr className="rule" />
          <ul className="tight">
            <li>The signal is a guidance / post-filing-drift bet — filings are public and priced fast; any edge lives in the drift.</li>
            <li>COPX carries ~28% single-name concentration, so ETF tracking of the material thesis is imperfect.</li>
            <li>The consumer signal rests on a handful of filings; one large revision could move the z-score by ±0.1.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
