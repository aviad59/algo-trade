import { FORECAST_QUARTER, TRACKER } from "../data/fixtures";
import { pct, signed } from "../lib/format";
import { LiveBadge } from "./ui";

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
        <p className="card-title">How the pick is doing</p>
        <p className="card-sub">Tracking starts once the quarter is underway.</p>
      </div>
    );
  }

  const beatEq = t.scorecard?.find((s) => s.label === "Equal-weight")?.beat ?? false;
  const n = (t.actual ?? []).filter((a) => a.rank != null).length;
  const byMat: Record<string, { qtd: number | null; rank: number | null }> = {};
  (t.actual ?? []).forEach((a) => (byMat[a.material] = { qtd: a.qtd, rank: a.rank }));

  return (
    <div className="card section-gap" style={{ borderLeft: `3px solid var(${beatEq ? "--good" : "--bad"})` }}>
      <div className="tracker-head">
        <p className="card-title" style={{ margin: 0 }}>How the pick is doing</p>
        <LiveBadge label="Live" />
        <span className="tracker-asof mono">{fmtAsOf(t.asOf)}</span>
      </div>

      <div className="tracker-line">
        <span className="tracker-num mono" style={{ color: (t.pick.qtd ?? 0) >= 0 ? "var(--good-text)" : "var(--bad-text)" }}>
          {t.pick.qtd == null ? "—" : pct(t.pick.qtd)}
        </span>
        <span className="tracker-sub">
          {t.pick.material} <span className="tk">{t.pick.etf}</span> · #{t.pick.actualRank ?? "—"} of {n} so far ·{" "}
          <span className={beatEq ? "pos" : "neg"}>{beatEq ? "ahead of" : "behind"}</span> all six
        </span>
      </div>

      <div className="qtd-progress live">
        <div className="qtd-progress-fill" style={{ width: `${t.pctElapsed ?? 0}%` }} />
      </div>
      <div className="qtd-scale">
        <span>quarter started</span>
        <span className="mono">{t.pctElapsed}% done</span>
        <span>quarter ends</span>
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
        Not final — the order can still change until {FORECAST_QUARTER} closes.
      </p>
    </div>
  );
}
