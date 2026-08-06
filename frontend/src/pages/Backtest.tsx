import { useState } from "react";
import { PredictionSlope } from "../components/charts/PredictionSlope";
import { AiMark } from "../components/ui";
import { QUARTER_REPORTS } from "../data/fixtures";
import type { EvidenceItem, QuarterReport } from "../data/types";
import { pct, signed } from "../lib/format";

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Beat = the pick outperformed the equal-weight materials basket that quarter. */
function isWin(r: QuarterReport): boolean {
  const eq = r.scorecard.find((s) => s.label === "Equal-weight");
  return eq ? eq.beat : false;
}

/** Profit = the pick actually made money, regardless of how the basket did. */
function madeMoney(r: QuarterReport): boolean {
  return r.pick.return >= 0;
}

/* -------- ① quarter picker strip --------
   Two independent facts per quarter, never conflated:
     dot colour = did the pick make money
     ring       = did it beat owning all six metals
   A red dot with a ring is a real outcome: everything fell, we fell less. */
function QuarterPicker({
  reports, active, onPick,
}: { reports: QuarterReport[]; active: number; onPick: (i: number) => void }) {
  return (
    <>
      <div className="qpick" role="tablist" aria-label="Pick a quarter">
        {reports.map((r, i) => {
          const up = madeMoney(r);
          const beat = isWin(r);
          const eq = r.scorecard.find((s) => s.label === "Equal-weight");
          return (
            <button
              key={r.short}
              role="tab"
              aria-selected={i === active}
              className={`qpick-chip ${i === active ? "active" : ""} ${up ? "up" : "down"}${beat ? " beat" : ""}`}
              onClick={() => onPick(i)}
              title={
                `${r.quarter} — picked ${r.pick.material}, ${up ? "made" : "lost"} ${pct(Math.abs(r.pick.return))}` +
                (eq ? `; all six metals ${pct(eq.benchmark)} → ${beat ? "we beat the basket" : "the basket beat us"}` : "")
              }
            >
              <span className="qp-q">{r.short}</span>
              <span className="qp-dot" />
            </button>
          );
        })}
      </div>
      <div className="qpick-legend">
        <span className="li"><span className="qp-key up" /> made money</span>
        <span className="li"><span className="qp-key down" /> lost money</span>
        <span className="li"><span className="qp-key down beat" /> ring = still beat owning all six</span>
      </div>
    </>
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
        <p className="card-title">What we predicted</p>
        <p className="card-sub">Ranked on {fmtDate(report.decisionDate)}, before the quarter began.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th>Metal</th><th className="num">Score</th><th className="num">Finished</th></tr>
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
          ▲ did better than we expected · ▼ did worse.
        </p>
      </div>

      <div className="card">
        <p className="card-title">What actually happened</p>
        <p className="card-sub">Best to worst, {fmtDate(report.windowStart)} – {fmtDate(report.windowEnd)}.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th>Metal</th><th className="num">Return</th></tr>
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
          Our pick finished <strong style={{ color: "var(--ink)" }}>#{report.pick.actualRank ?? "—"} of {n}</strong>
        </p>
      </div>
    </div>
  );
}

/* -------- the filings that drove the pick -------- */
function Evidence({ items, material }: { items: EvidenceItem[]; material: string }) {
  if (!items.length) {
    return <p className="footnote">No filings fed the {material} score this quarter.</p>;
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
          <div className="eyebrow">Step 5 — the scorecard</div>
          <h1>Did the picks actually work?</h1>
        </div>
        <div className="card"><p className="empty-row">No finished quarters to score yet.</p></div>
      </div>
    );
  }

  const r = reports[active];
  const win = isWin(r);
  const n = r.actual.filter((a) => a.rank != null).length;

  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Step 5 — the scorecard</div>
        <h1>Did the picks actually work?</h1>
        <p className="page-desc">What we predicted at the time, and what the price actually did.</p>
      </div>

      {/* ① pick a quarter */}
      <p className="pick-hint">Choose a quarter</p>
      <QuarterPicker reports={reports} active={active} onPick={setActive} />

      {/* the call */}
      <div className="card call-hero section-gap" style={{ borderLeft: `3px solid var(${win ? "--good" : "--bad"})` }}>
        <div className="split" style={{ gridTemplateColumns: "1.5fr 1fr", gap: 26 }}>
          <div>
            <div className="kpi-label" style={{ marginBottom: 8 }}>
              {r.quarter} · {fmtDate(r.windowStart)} – {fmtDate(r.windowEnd)}
            </div>
            <div className="verdict-line">
              We picked <strong style={{ color: "var(--ink)" }}>{r.pick.material}</strong>{" "}
              <span className="tk">{r.pick.etf}</span>. It returned{" "}
              <span className={r.pick.realized != null && r.pick.realized >= 0 ? "pos" : "neg"}>
                {r.pick.realized == null ? "—" : pct(r.pick.realized)}
              </span> and finished <strong style={{ color: "var(--ink)" }}>#{r.pick.actualRank ?? "—"} of {n}</strong>{" "}
              — <span className={win ? "pos" : "neg"}>{win ? "better" : "worse"}</span> than owning all six.
            </div>
            {r.rating?.prose && (
              <div className="ev-quote" style={{ marginTop: 12 }}>
                {r.rating.prose}
                <span className="src">
                  <AiMark size={11} /> What our AI wrote at the time, {fmtDate(r.decisionDate)} — before any of this had happened
                </span>
              </div>
            )}
            <p className="footnote" style={{ marginTop: 10 }}>
              Yahoo Finance prices, trading costs included. Nothing filed after {fmtDate(r.decisionDate)} informed the pick.
            </p>
          </div>
          <div className="call-hero-num">
            <div className="kpi-label">Pick return</div>
            <div className="hero-num" style={{ color: `var(${r.pick.return >= 0 ? "--good-text" : "--bad-text"})`, fontSize: 40 }}>
              {pct(r.pick.return)}
            </div>
            <div className="kpi-note">
              market {pct(r.baselines.spy)} · all six metals {pct(r.baselines.eqweight)}
            </div>
          </div>
        </div>
      </div>

      {/* why the AI picked it — sits right under the headline number, collapsed */}
      <details className="card section-gap disclose">
        <summary>
          <span>
            <span className="disclose-title">
              <AiMark size={13} /> Find out why our AI picked {r.pick.material}
            </span>
            <span className="disclose-sub">
              {r.evidence.length} filing{r.evidence.length === 1 ? "" : "s"} drove this call
            </span>
          </span>
          <span className="disclose-chev" aria-hidden="true">▾</span>
        </summary>
        <div className="disclose-body">
          <Evidence items={r.evidence} material={r.pick.material} />
        </div>
      </details>

      {/* the first graph: what we predicted vs how the ETF actually moved */}
      <div className="card section-gap">
        <p className="card-title">Our call vs what the price did</p>
        <p className="card-sub">
          Solid = how {r.pick.etf} moved. Dashed = how confident we were. Same direction = right call.
        </p>
        <PredictionSlope report={r} />
      </div>

      {/* prediction vs reality */}
      <div className="section-gap">
        <PredVsActual report={r} />
      </div>

    </div>
  );
}
