import { CompareBars } from "./charts/CompareBars";
import { FORECAST_QUARTER, TRACKER } from "../data/fixtures";
import { pct, signed } from "../lib/format";

function fmtAsOf(s?: string): string {
  if (!s) return "";
  if (s.includes(",")) return s; // already formatted
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Live report card for the in-progress quarter, built around the one question
 * that matters: is the pick beating the market so far? The ranking was fixed at
 * the quarter's open; prices move daily.
 */
export function ForecastTracker() {
  const t = TRACKER;
  if (!t?.available || !t.pick) {
    return (
      <div className="card section-gap">
        <p className="card-title">How the pick is doing</p>
        <p className="empty-note" style={{ padding: "14px 0 4px" }}>
          Nothing to track yet — this starts filling in once the quarter is underway and prices are loaded.
        </p>
      </div>
    );
  }

  const n = (t.actual ?? []).filter((a) => a.rank != null).length;
  const byMat: Record<string, { qtd: number | null; rank: number | null }> = {};
  (t.actual ?? []).forEach((a) => (byMat[a.material] = { qtd: a.qtd, rank: a.rank }));

  return (
    <div className="card section-gap">
      <div className="tracker-head">
        <p className="card-title" style={{ margin: 0 }}>How the pick is doing so far</p>
        <span className="chip accent">in progress</span>
        <span className="tracker-asof mono">prices through {fmtAsOf(t.asOf)}</span>
      </div>
      <p className="card-sub" style={{ marginTop: 4 }}>
        {t.pick.material} <span className="tk">{t.pick.etf}</span> against what else you could have bought,
        since the quarter began.
      </p>

      <CompareBars
        rows={[
          { label: `${t.pick.material} — our pick`, value: t.pick.qtd, colorVar: "--c-strategy", emphasis: true },
          { label: "The market (SPY)", value: t.baselines?.spy ?? null, colorVar: "--c-market" },
          { label: "All six metals", value: t.baselines?.eqweight ?? null, colorVar: "--c-basket" },
        ]}
      />

      <div className="qtd-progress">
        <div className="qtd-progress-fill" style={{ width: `${t.pctElapsed ?? 0}%` }} />
      </div>
      <div className="qtd-scale">
        <span>quarter started</span>
        <span className="mono">{t.pctElapsed ?? 0}% done</span>
        <span>quarter ends</span>
      </div>

      {(t.predicted ?? []).length > 0 && (
        <details className="disclose disclose-inline">
          <summary>
            <span>
              <span className="disclose-title">All six metals so far</span>
              <span className="disclose-sub">Our predicted order against the actual price moves to date</span>
            </span>
            <span className="disclose-chev" aria-hidden="true" />
          </summary>
          <div className="disclose-body">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>We said</th><th>Metal</th><th className="num">Score</th><th className="num">So far</th><th className="num">Rank now</th></tr>
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
              #{t.pick.actualRank ?? "—"} of {n} so far. Not final — the order can still change.
              When {FORECAST_QUARTER || "the quarter"} closes, this becomes one more row on the “Did it work?” page.
            </p>
          </div>
        </details>
      )}
    </div>
  );
}
