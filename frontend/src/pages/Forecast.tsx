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

/** Inline score bar: shared scale across the six rows, zero in the middle. */
function ScoreBar({ z, max }: { z: number; max: number }) {
  const half = 50; // % of track on each side of zero
  const w = Math.min(Math.abs(z) / max, 1) * half;
  return (
    <span className="score-track" aria-hidden="true">
      <span className="score-zero" />
      <span
        className="score-fill"
        style={{
          left: z >= 0 ? "50%" : `${50 - w}%`,
          width: `${w}%`,
          background: z >= 0 ? "var(--c-strategy)" : "var(--axis)",
        }}
      />
    </span>
  );
}

export function Forecast() {
  if (!MATERIALS.length) {
    return (
      <div className="page">
        <div className="page-head rise">
          <div className="eyebrow">The pick</div>
          <h1>This quarter's pick</h1>
        </div>
        <div className="card rise d1">
          <p className="empty-note">
            <strong>No forecast loaded.</strong>
            The backend isn't running, or no quarter has been scored yet — so there is nothing to show,
            and nothing here is made up. Start the backend and reload to see the current ranking.
          </p>
        </div>
      </div>
    );
  }

  const pick = MATERIALS[0];
  const margin = MATERIALS.length > 1 ? pick.z - MATERIALS[1].z : 0;
  const confidence = margin >= 0.5 ? "High" : margin >= 0.25 ? "Moderate" : "Low";
  const zmax = Math.max(...MATERIALS.map((m) => Math.abs(m.z)), 0.01);
  // Agent #2's stored recommendation — only shown if it's actually about this pick
  const rating = PICK_RATING && PICK_RATING.material === pick.material ? PICK_RATING : null;
  const quote = rating?.supporting?.[0] ?? null;

  return (
    <div className="page">
      <div className="page-head rise">
        <div className="eyebrow">The pick</div>
        <h1>This quarter's pick{FORECAST_QUARTER ? ` — ${FORECAST_QUARTER}` : ""}</h1>
        {PUBLISHED_DATE && (
          <p className="page-desc">
            Decided on {PUBLISHED_DATE} from {FILINGS_DIGESTED.toLocaleString()} reports filed up to the end of {PRIOR_QUARTER}.
            Nothing filed later was used.
          </p>
        )}
      </div>

      <div className="card hero-card rise d1">
        <div className="hero-grid">
          <div>
            <div className="kpi-label">Buy one metal's miner fund — this one</div>
            <div className="hero-num" style={{ marginTop: 8 }}>{pick.material}</div>
            <div className="hero-etf">
              <span className="tk" style={{ fontSize: 18, color: "var(--accent-ink)" }}>{pick.etf}</span>
              <span style={{ color: "var(--ink-3)", fontSize: 15 }}>{ETF_NAMES[pick.etf] ?? ""}</span>
            </div>
            <div className="hero-stats">
              <div><div className="kpi-label">Score</div><div className="kpi-value mono" style={{ fontSize: 27 }}>{signed(pick.z)}</div></div>
              <div><div className="kpi-label">Confidence</div><div className="kpi-value" style={{ fontSize: 27 }}>{confidence}</div></div>
              <div><div className="kpi-label">Lead over #2</div><div className="kpi-value mono" style={{ fontSize: 27 }}>{signed(margin)}</div></div>
            </div>
            {quote && (
              <div className="ev-quote" style={{ marginTop: 18 }}>
                “{quote.quote.replace(/^[“"]|[”"]$/g, "")}”
                <span className="src">{quote.ticker} — one of the filings behind this score</span>
              </div>
            )}
          </div>

          {/* the full standings, right in the pick card */}
          <div className="mini-rank">
            <div className="kpi-label" style={{ marginBottom: 8 }}>All six, ranked</div>
            <table className="mini-rank-table">
              <tbody>
                {MATERIALS.map((m) => (
                  <tr key={m.material} className={m.rank === 1 ? "row-pick" : undefined}>
                    <td><span className={`rank-chip${m.rank === 1 ? " top" : ""}`}>{m.rank}</span></td>
                    <td style={{ fontWeight: m.rank === 1 ? 650 : 500 }}>{m.material}</td>
                    <td><span className="tk">{m.etf}</span></td>
                    <td className="score-cell"><ScoreBar z={m.z} max={zmax} /></td>
                    <td className={`num ${m.z >= 0 ? "pos" : "neg"}`}>{signed(m.z)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="footnote" style={{ marginTop: 10 }}>
              Score = how far each metal's filing evidence sits above or below the average of the six.
              Positive means stronger than the pack.
            </p>
          </div>
        </div>

        {/* the AI's reasoning — one click away, never in your face */}
        {rating ? (
          <details className="disclose disclose-inline">
            <summary>
              <span>
                <span className="disclose-title">
                  <AiMark size={15} /> Why {pick.material.toLowerCase()}? Read the write-up
                </span>
                <span className="disclose-sub">What our AI wrote about this ranking</span>
              </span>
              <span className="disclose-chev" aria-hidden="true" />
            </summary>
            <div className="disclose-body">
              <p style={{ margin: 0, fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)" }}>{rating.prose}</p>
              {rating.supporting.length > 1 && (
                <div style={{ marginTop: 12 }}>
                  {rating.supporting.slice(1).map((s, i) => (
                    <div className="ev-quote" key={`${s.ticker}-${i}`}>
                      “{s.quote.replace(/^[“"]|[”"]$/g, "")}”
                      <span className="src">{s.ticker} · cited by our AI</span>
                    </div>
                  ))}
                </div>
              )}
              <p className="footnote" style={{ marginTop: 10 }}>
                Written by our AI{rating.model ? ` · ${rating.model}` : ""}. It explains the ranking — it can't change it.
              </p>
            </div>
          </details>
        ) : (
          <p className="footnote" style={{ marginTop: 18 }}>
            No AI write-up stored for this quarter. The ranking stands on its own.
          </p>
        )}
      </div>

      <div className="rise d2">
        <ForecastTracker />

        <div className="card section-gap">
          <p className="card-title">Where each score came from</p>
          <p className="card-sub">
            Two kinds of clues: from the companies that mine each metal, and from the ones that buy it.
            “—” means no buyer-side reports mention that metal.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th><th>Metal</th><th>Fund</th>
                  <th className="num">Score</th><th className="num">From miners</th><th className="num">From buyers</th><th className="num">Reports</th>
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
      </div>
    </div>
  );
}
