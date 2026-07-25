import { FORECAST_QUARTER, TRACKER } from "../data/fixtures";
import { pct, signed } from "../lib/format";

function fmtAsOf(s?: string): string {
  if (!s) return "";
  if (s.includes(",")) return s; // already formatted (fixture)
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Live report card for the in-progress forecast quarter: the ranking fixed at
 * the quarter's open, tracked against each ETF's quarter-to-date move, with a
 * provisional rank-IC and "on track?" verdict.
 */
export function ForecastTracker() {
  const t = TRACKER;
  if (!t?.available || !t.pick) {
    return (
      <div className="card section-gap">
        <p className="card-title">How this forecast is doing so far</p>
        <p className="card-sub">Tracking begins once the quarter is underway and prices are in.</p>
      </div>
    );
  }

  const beatEq = t.scorecard?.find((s) => s.label === "Equal-weight")?.beat ?? false;
  const n = (t.actual ?? []).filter((a) => a.rank != null).length;
  const byMat: Record<string, { qtd: number | null; rank: number | null }> = {};
  (t.actual ?? []).forEach((a) => (byMat[a.material] = { qtd: a.qtd, rank: a.rank }));

  return (
    <div className="card section-gap" style={{ borderLeft: `3px solid var(${beatEq ? "--good" : "--bad"})` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <p className="card-title" style={{ margin: 0 }}>How this forecast is doing so far</p>
        <span className="pill" style={{ borderColor: "var(--warn)", color: "var(--warn)" }}>Provisional · in progress</span>
      </div>
      <p className="card-sub">
        {t.pctElapsed}% through {FORECAST_QUARTER} · quarter-to-date through {fmtAsOf(t.asOf)}. The ranking was fixed at
        the quarter's open; these are the ETFs' real moves since.
      </p>

      <div className="qtd-progress"><div className="qtd-progress-fill" style={{ width: `${t.pctElapsed ?? 0}%` }} /></div>

      <div className="grid g4 section-gap" style={{ marginTop: 16 }}>
        <div className="card kpi">
          <div className="kpi-label">Pick QTD return</div>
          <div className="kpi-value mono" style={{ fontSize: 21, color: (t.pick.qtd ?? 0) >= 0 ? "var(--good-text)" : "var(--bad-text)" }}>
            {t.pick.qtd == null ? "—" : pct(t.pick.qtd)}
          </div>
          <div className="kpi-note">{t.pick.material} · {t.pick.etf}</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Standing so far</div>
          <div className="kpi-value" style={{ fontSize: 21 }}>#{t.pick.actualRank ?? "—"} <span style={{ fontSize: 13, color: "var(--ink-3)" }}>of {n}</span></div>
          <div className="kpi-note">predicted #{t.pick.predictedRank}</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Rank-IC (QTD)</div>
          <div className="kpi-value mono" style={{ fontSize: 21 }}>{t.rankIC == null ? "—" : signed(t.rankIC, 2)}</div>
          <div className="kpi-note">pred rank vs QTD rank</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">On track?</div>
          <div className="kpi-value" style={{ fontSize: 21 }}><span className={beatEq ? "pos" : "neg"}>{beatEq ? "On track" : "Behind"}</span></div>
          <div className="kpi-note">vs equal-weight basket</div>
        </div>
      </div>

      <div className="table-wrap section-gap">
        <table>
          <thead>
            <tr><th>Pred #</th><th>Material</th><th className="num">z</th><th className="num">QTD</th><th className="num">Now</th></tr>
          </thead>
          <tbody>
            {(t.predicted ?? []).slice().sort((a, b) => a.rank - b.rank).map((p) => {
              const a = byMat[p.material];
              const move = a?.rank == null ? 0 : p.rank - a.rank;
              const isPick = p.material === t.pick!.material;
              return (
                <tr key={p.material} className={`hoverable-row ${isPick ? "row-pick" : ""}`}>
                  <td><span className={`rank-chip ${p.rank === 1 ? "top" : ""}`}>{p.rank}</span></td>
                  <td>{p.material} <span className="tk">{p.etf}</span></td>
                  <td className={`num ${p.z >= 0 ? "pos" : "neg"}`}>{signed(p.z, 2)}</td>
                  <td className={`num ${a?.qtd == null ? "" : a.qtd >= 0 ? "pos" : "neg"}`}>{a?.qtd == null ? "—" : pct(a.qtd)}</td>
                  <td className="num">
                    {a?.rank == null ? "—" : (
                      <span className={move > 0 ? "pos" : move < 0 ? "neg" : ""}>
                        #{a.rank}{move !== 0 ? ` ${move > 0 ? "▲" : "▼"}${Math.abs(move)}` : ""}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="footnote" style={{ marginTop: 10 }}>
        Provisional — only {t.pctElapsed}% of the quarter has elapsed, so ranks can still change. The final,
        full-quarter verdict lands in the Backtest once {FORECAST_QUARTER} closes.
      </p>
    </div>
  );
}
