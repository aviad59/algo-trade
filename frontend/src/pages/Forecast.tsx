import { ForecastTracker } from "../components/ForecastTracker";
import { AiMark } from "../components/ui";
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
        <div className="eyebrow">Steps 3 &amp; 4 — the pick</div>
        <h1>This quarter's pick — {FORECAST_QUARTER}</h1>
        <p className="page-desc">
          Decided on {PUBLISHED_DATE} from {FILINGS_DIGESTED} reports filed up to the end of {PRIOR_QUARTER}.
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
              <div><div className="kpi-label">Score</div><div className="kpi-value mono" style={{ fontSize: 22 }}>{signed(pick.z)}</div></div>
              <div><div className="kpi-label">Confidence</div><div className="kpi-value" style={{ fontSize: 22 }}>{confidence}</div></div>
              <div><div className="kpi-label">Lead over #2</div><div className="kpi-value mono" style={{ fontSize: 22 }}>{signed(margin)}</div></div>
            </div>
          </div>

          {/* who it beat — the compact standings, right in the pick card */}
          <div className="mini-rank">
            <div className="kpi-label" style={{ marginBottom: 8 }}>What it beat</div>
            <table className="mini-rank-table">
              <tbody>
                {MATERIALS.map((m) => (
                  <tr key={m.material} className={m.rank === 1 ? "row-pick" : undefined}>
                    <td><span className={`rank-chip${m.rank === 1 ? " top" : ""}`}>{m.rank}</span></td>
                    <td style={{ fontWeight: m.rank === 1 ? 650 : 500 }}>{m.material}</td>
                    <td><span className="tk">{m.etf}</span></td>
                    <td className={`num ${m.z >= 0 ? "pos" : "neg"}`}>{signed(m.z)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* the AI's reasoning — one click away, never in your face */}
        {rating ? (
          <details className="disclose disclose-inline">
            <summary>
              <span>
                <span className="disclose-title">
                  <AiMark size={13} /> See why our AI picked {pick.material.toLowerCase()}
                </span>
                <span className="disclose-sub">Its write-up for {FORECAST_QUARTER}</span>
              </span>
              <span className="disclose-chev" aria-hidden="true">▾</span>
            </summary>
            <div className="disclose-body">
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-2)" }}>{rating.prose}</p>
              <p className="footnote" style={{ marginTop: 10 }}>
                Written by our AI{rating.model ? ` · ${rating.model}` : ""}. It explains the ranking, it can't change it.
              </p>
            </div>
          </details>
        ) : (
          <p className="footnote" style={{ marginTop: 18 }}>
            No AI write-up yet. The ranking stands on its own.
          </p>
        )}
      </div>

      <ForecastTracker />

      <div className="card section-gap">
        <p className="card-title">Where each score came from</p>
        <p className="card-sub">Split by who said it: miners, or the companies that buy from them.</p>
        <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th><th>Metal</th><th>Fund</th>
                  <th className="num">Score</th><th className="num">Miners</th><th className="num">Buyers</th><th className="num">Reports</th>
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

      <div className="section-gap split">
        <div className="card">
          <p className="card-title"><AiMark size={13} /> The quotes our AI leaned on</p>
          <p className="card-sub">Straight from the filings.</p>
          {rating && rating.supporting.length > 0 ? (
            <div>
              {rating.supporting.map((s, i) => (
                <div className="ev-quote" key={`${s.ticker}-${i}`}>
                  “{s.quote.replace(/^[“"]|[”"]$/g, "")}”
                  <span className="src">{s.ticker} · cited by our AI</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="footnote">No quotes stored yet.</p>
          )}
        </div>
        <div className="card" style={{ borderLeft: "3px solid var(--bad)" }}>
          <p className="card-title">What could go wrong</p>
          <p className="card-sub">The evidence pointing the other way.</p>
          <span className="ev-tag bear">▼ Negative · a miner</span>
          <div className="ev-quote">
            “We are experiencing softening demand in Chinese construction end-markets and expect volume headwinds to persist through fiscal 2026.”
            <span className="src">SCCO · 10-Q · 2026-06-30</span>
          </div>
          <hr className="rule" />
          <ul className="tight">
            <li>Filings are public instantly and markets move fast — any edge is in the slow drift after.</li>
            <li>The fund isn't the metal: ~28% of COPX sits in one company.</li>
            <li>The demand signal rests on a handful of reports. One revision could shift it.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
