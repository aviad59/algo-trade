import { useState } from "react";
import { EquityCurve } from "../components/charts/EquityCurve";
import { PredictionSlope } from "../components/charts/PredictionSlope";
import { RankICChart } from "../components/charts/RankICChart";
import { DECOMP, METRICS, QUARTER_REPORTS } from "../data/fixtures";
import type { EvidenceItem, QuarterReport, ScorecardItem } from "../data/types";
import { pct, signed } from "../lib/format";

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Win = the pick beat the equal-weight materials basket that quarter. */
function isWin(r: QuarterReport): boolean {
  const eq = r.scorecard.find((s) => s.label === "Equal-weight");
  return eq ? eq.beat : false;
}

/* -------- ① quarter picker strip -------- */
function QuarterPicker({
  reports, active, onPick,
}: { reports: QuarterReport[]; active: number; onPick: (i: number) => void }) {
  return (
    <div className="qpick" role="tablist" aria-label="Pick a quarter">
      {reports.map((r, i) => (
        <button
          key={r.short}
          role="tab"
          aria-selected={i === active}
          className={`qpick-chip ${i === active ? "active" : ""} ${isWin(r) ? "win" : "loss"}`}
          onClick={() => onPick(i)}
          title={`${r.quarter} — pick ${r.pick.material} ${r.pick.realized == null ? "" : pct(r.pick.realized)}`}
        >
          <span className="qp-q">{r.short}</span>
          <span className="qp-dot" />
        </button>
      ))}
    </div>
  );
}

/* -------- ② scorecard: pick vs each baseline, this quarter -------- */
function Scorecard({ pickReturn, items }: { pickReturn: number; items: ScorecardItem[] }) {
  return (
    <div className="grid g4">
      {items.map((s) => (
        <div className="card kpi" key={s.label}>
          <div className="kpi-label">vs {s.label}</div>
          <div className="kpi-value" style={{ fontSize: 19 }}>
            <span className={s.beat ? "pos" : "neg"}>{s.beat ? "Beat" : "Trails"}</span>{" "}
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>{pct(s.delta)}</span>
          </div>
          <div className="kpi-note mono" style={{ fontSize: 11.5 }}>
            pick {pct(pickReturn)} · {s.label} {pct(s.benchmark)}
          </div>
        </div>
      ))}
    </div>
  );
}

/* -------- predicted ranking ↔ what actually happened -------- */
function PredVsActual({ report }: { report: QuarterReport }) {
  const actRank: Record<string, number | null> = {};
  report.actual.forEach((a) => (actRank[a.material] = a.rank));
  const n = report.actual.filter((a) => a.rank != null).length;

  return (
    <div className="split" style={{ gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      <div className="card">
        <p className="card-title">Predicted ranking</p>
        <p className="card-sub">
          Point-in-time z-score as of {fmtDate(report.decisionDate)} — using only filings public before the quarter began.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th>Material</th><th className="num">z</th><th className="num">Landed</th></tr>
            </thead>
            <tbody>
              {report.predicted.slice().sort((a, b) => a.rank - b.rank).map((p) => {
                const ar = actRank[p.material];
                const move = ar == null ? 0 : p.rank - ar; // + = did better than predicted
                const pick = p.material === report.pick.material;
                return (
                  <tr key={p.material} className={`hoverable-row ${pick ? "row-pick" : ""}`}>
                    <td><span className={`rank-chip ${p.rank === 1 ? "top" : ""}`}>{p.rank}</span></td>
                    <td>{p.material} <span className="tk">{p.etf}</span></td>
                    <td className={`num ${p.z >= 0 ? "pos" : "neg"}`}>{signed(p.z, 2)}</td>
                    <td className="num">
                      {ar == null ? "—" : (
                        <span className={move > 0 ? "pos" : move < 0 ? "neg" : ""}>
                          #{ar}{move !== 0 ? ` ${move > 0 ? "▲" : "▼"}${Math.abs(move)}` : ""}
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
          "Landed" = where each material actually finished. ▲ beat its forecast rank, ▼ underperformed it.
        </p>
      </div>

      <div className="card">
        <p className="card-title">What actually happened</p>
        <p className="card-sub">
          Realized ETF total return over {fmtDate(report.windowStart)} – {fmtDate(report.windowEnd)}, ranked best to worst.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th>Material</th><th className="num">Realized</th></tr>
            </thead>
            <tbody>
              {report.actual.map((a) => {
                const pick = a.material === report.pick.material;
                return (
                  <tr key={a.material} className={`hoverable-row ${pick ? "row-pick" : ""}`}>
                    <td><span className={`rank-chip ${a.rank === 1 ? "top" : ""}`}>{a.rank ?? "—"}</span></td>
                    <td>{a.material} <span className="tk">{a.etf}</span></td>
                    <td className={`num ${a.realized == null ? "" : a.realized >= 0 ? "pos" : "neg"}`}>
                      {a.realized == null ? "—" : pct(a.realized)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="footnote" style={{ marginTop: 10 }}>
          Our pick finished <strong style={{ color: "var(--ink)" }}>#{report.pick.actualRank ?? "—"} of {n}</strong>.
          {report.rankIC != null && <> Quarter rank-IC {signed(report.rankIC, 2)}.</>}
        </p>
      </div>
    </div>
  );
}

/* -------- the filings that drove the pick -------- */
function Evidence({ items, material }: { items: EvidenceItem[]; material: string }) {
  if (!items.length) {
    return <p className="footnote">No extracted filings contributed to the {material} score this quarter.</p>;
  }
  return (
    <div className="ev-list">
      {items.map((e, i) => {
        const tag = e.direction === "increase" ? "bull" : "bear";
        return (
          <div className="ev-item" key={`${e.ticker}-${i}`}>
            <div className="ev-item-head">
              <span className="tk">{e.ticker}</span>
              <span className="chip">{e.form}</span>
              <span className={`ev-tag ${tag}`}>{e.direction === "increase" ? "▲" : "▼"} {e.magnitude}</span>
              <span className={`pill ${e.perspective === "producer" ? "persp-p" : "persp-c"}`}>{e.perspective}</span>
              <span className="ev-weight mono">weight {signed(e.weight, 2)}</span>
              <span className="ev-date mono">{fmtDate(e.filingDate)}</span>
            </div>
            <div className="ev-quote">{e.quote}<span className="src">{e.company}</span></div>
          </div>
        );
      })}
    </div>
  );
}

export function Backtest() {
  const reports = QUARTER_REPORTS;
  const [active, setActive] = useState(Math.max(0, reports.length - 1));

  if (!reports.length) {
    return (
      <div className="page">
        <div className="page-head">
          <div className="eyebrow">Evaluation · point-in-time</div>
          <h1>Backtest</h1>
        </div>
        <div className="card"><p className="empty-row">No backtested quarters yet — seed the buffer and price history first.</p></div>
      </div>
    );
  }

  const r = reports[active];
  const win = isWin(r);
  const n = r.actual.filter((a) => a.rank != null).length;

  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Evaluation · point-in-time · quarter by quarter</div>
        <h1>How did each quarter's pick actually do?</h1>
        <p className="page-desc">
          Pick a quarter. See exactly what the recommender predicted using only information available at the time,
          what really happened over that quarter, and whether the single-ETF bet beat the market — with the filings
          that drove the call.
        </p>
      </div>

      {/* ① pick a quarter */}
      <QuarterPicker reports={reports} active={active} onPick={setActive} />

      {/* the call */}
      <div className="card call-hero section-gap" style={{ borderLeft: `3px solid var(${win ? "--good" : "--bad"})` }}>
        <div className="split" style={{ gridTemplateColumns: "1.5fr 1fr", gap: 26 }}>
          <div>
            <div className="kpi-label" style={{ marginBottom: 8 }}>
              {r.quarter} · {fmtDate(r.windowStart)} – {fmtDate(r.windowEnd)}
            </div>
            <div className="verdict-line">
              Picked <strong style={{ color: "var(--ink)" }}>{r.pick.material}</strong>{" "}
              <span className="tk">{r.pick.etf}</span> — ranked #{r.pick.predictedRank ?? "—"} at z {signed(r.pick.z, 2)}.
              It returned <span className={r.pick.realized != null && r.pick.realized >= 0 ? "pos" : "neg"}>
                {r.pick.realized == null ? "—" : pct(r.pick.realized)}
              </span>, finishing <strong style={{ color: "var(--ink)" }}>#{r.pick.actualRank ?? "—"} of {n}</strong>{" "}
              — it <span className={win ? "pos" : "neg"}>{win ? "beat" : "trailed"}</span> the equal-weight basket.
            </div>
            {r.rating?.prose && (
              <div className="ev-quote" style={{ marginTop: 12 }}>
                {r.rating.prose}
                <span className="src">
                  Agent #2's stored recommendation for {r.quarter} — written from filings public before {fmtDate(r.decisionDate)}
                </span>
              </div>
            )}
            <p className="footnote" style={{ marginTop: 10 }}>
              Strategy: hold the top-ranked miner ETF for the quarter, 10 bps rotation cost, dividend-adjusted closes.
              The rank uses only filings public before {fmtDate(r.decisionDate)}.
            </p>
          </div>
          <div className="call-hero-num">
            <div className="kpi-label">Pick return</div>
            <div className="hero-num" style={{ color: `var(${r.pick.return >= 0 ? "--good-text" : "--bad-text"})`, fontSize: 40 }}>
              {pct(r.pick.return)}
            </div>
            <div className="kpi-note">vs SPY {pct(r.baselines.spy)} · eq-wt {pct(r.baselines.eqweight)}</div>
          </div>
        </div>
      </div>

      {/* the first graph: what we predicted vs how the ETF actually moved */}
      <div className="card section-gap">
        <p className="card-title">Prediction vs the ETF's actual move</p>
        <p className="card-sub">
          Both lines start together at the quarter's open. Solid = how {r.pick.etf} actually moved (left axis, %);
          dashed = our prediction, the cross-sectional conviction z-score (right axis, σ). Same direction = the call
          was right.
        </p>
        <PredictionSlope report={r} />
      </div>

      {/* ② did it beat the baselines — this quarter */}
      <div className="section-gap">
        <Scorecard pickReturn={r.pick.return} items={r.scorecard} />
      </div>

      {/* prediction vs reality */}
      <div className="section-gap">
        <PredVsActual report={r} />
      </div>

      {/* the evidence */}
      <div className="card section-gap">
        <p className="card-title">Why {r.pick.material} — the filings that drove the pick</p>
        <p className="card-sub">
          Every effect public before {fmtDate(r.decisionDate)} whose window overlapped this quarter, ranked by its
          recency-weighted contribution. Note the range of filing dates — a quarter is informed by several quarters of
          filings, not just the previous one.
        </p>
        <Evidence items={r.evidence} material={r.pick.material} />
      </div>

      {/* whole-period context */}
      <div className="card section-gap">
        <p className="card-title">Across the full backtest window</p>
        <p className="card-sub">
          Growth of $100 following the top-1 rotation vs the four baselines — the aggregate picture behind the
          quarter-by-quarter calls above.
        </p>
        <EquityCurve />
        <div className="grid g6 section-gap" style={{ marginTop: 20 }}>
          {METRICS.map((m) => (
            <div className="card kpi" key={m.label}>
              <div className="kpi-label">{m.label}</div>
              <div className="kpi-value mono" style={{ fontSize: 20, color: m.bad ? "var(--bad-text)" : undefined }}>{m.value}</div>
              <div className="kpi-note">{m.note}</div>
            </div>
          ))}
        </div>
        <hr className="rule" />
        <div className="split" style={{ gridTemplateColumns: "1.4fr 1fr", gap: 26 }}>
          <div>
            <p className="card-title" style={{ fontSize: 13 }}>Rank information coefficient, per quarter</p>
            <p className="card-sub">Spearman correlation of forecast rank vs realized return rank. Mean {METRICS.find((m) => m.label === "Mean rank-IC")?.value ?? "—"}.</p>
            <RankICChart />
          </div>
          <div>
            <p className="card-title" style={{ fontSize: 13 }}>Perspective decomposition</p>
            <p className="card-sub" style={{ marginBottom: 10 }}>Does the demand signal add anything over producers?</p>
            {DECOMP.map((d) => (
              <div className="decomp-row" key={d.label}>
                <span style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{d.label}</span>
                <div className="decomp-track">
                  <div className="decomp-fill" style={{ background: `var(${d.colorVar})`, width: `${(d.ic / 0.4) * 50}%` }} />
                </div>
                <span className="mono" style={{ fontSize: 12.5, textAlign: "right" }}>{d.ic.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
