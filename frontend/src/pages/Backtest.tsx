import { useState } from "react";
import { CompareBars } from "../components/charts/CompareBars";
import { EquityCurve } from "../components/charts/EquityCurve";
import { AiMark } from "../components/ui";
import { METRICS, QUARTER_REPORTS } from "../data/fixtures";
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

/* -------- quarter picker strip --------
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
    <div className="split split-pva">
      <div className="card">
        <p className="card-title">What we predicted</p>
        <p className="card-sub">
          Our ranking on {fmtDate(report.decisionDate)}, before the quarter started.
        </p>
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
        <p className="card-sub">
          Real price moves, {fmtDate(report.windowStart)} – {fmtDate(report.windowEnd)}, best to worst.
        </p>
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
          Our pick finished <strong style={{ color: "var(--ink)" }}>#{report.pick.actualRank ?? "—"} of {n}</strong>.
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
              <span className={`pill ${e.perspective === "producer" ? "persp-p" : "persp-c"}`}>{e.perspective === "producer" ? "miner" : "buyer"}</span>
              <span className="ev-weight mono">pull on the score {signed(e.weight, 2)}</span>
              <span className="ev-date mono">{fmtDate(e.filingDate)}</span>
            </div>
            <div className="ev-quote">{e.quote}<span className="src">{e.company}</span></div>
          </div>
        );
      })}
    </div>
  );
}

/** Plain-English gloss for each overall metric, keyed by the API's label. */
const METRIC_GLOSS: Record<string, string> = {
  "CAGR": "average yearly growth of the $100",
  "Sharpe": "return earned per unit of risk taken",
  "Max drawdown": "worst fall from a high point along the way",
  "Hit rate": "how often the pick beat owning all six",
  "Mean rank-IC": "how well predicted order matched reality (1 = perfect, 0 = guessing)",
  "Regret vs best": "yearly gap to a picker with perfect foresight",
};

/* -------- the whole run, collapsed at the bottom -------- */
function WholeRun({ quarters }: { quarters: number }) {
  return (
    <details className="card disclose section-gap">
      <summary>
        <span>
          <span className="disclose-title">The whole run — every quarter added up</span>
          <span className="disclose-sub">
            $100 into every pick{quarters ? `, across ${quarters} finished quarters` : ""}, against the market — plus the honest fine print
          </span>
        </span>
        <span className="disclose-chev" aria-hidden="true" />
      </summary>
      <div className="disclose-body">
        <EquityCurve />
        <p className="footnote" style={{ marginTop: 12 }}>
          Real dividend-adjusted prices, trading costs included. Every pick used only filings public
          before its quarter began.
        </p>

        {METRICS.length > 0 && (
          <div className="metric-row section-gap">
            {METRICS.map((m) => (
              <div className="metric" key={m.label}>
                <div className="metric-label">{m.label}</div>
                <div className={`metric-value mono${m.bad ? " bad" : ""}`}>{m.value}</div>
                {METRIC_GLOSS[m.label] && <div className="metric-gloss">{METRIC_GLOSS[m.label]}</div>}
                {m.note && <div className="metric-note">{m.note}</div>}
              </div>
            ))}
          </div>
        )}

        <hr className="rule" />
        <p className="card-title">What these numbers don't prove</p>
        <ul className="tight">
          <li>
            {quarters > 0
              ? `Only ${quarters} finished quarters — enough to be promising, not enough to be proof.`
              : "Few finished quarters so far — enough to be promising, not enough to be proof."}
            {" "}The permutation p-value above says how easily luck alone could match this.
          </li>
          <li>Filings are public the moment they land and markets price them within minutes — this hunts the slow drift afterwards, which is a genuinely hard bet.</li>
          <li>Reports from non-US miners yield fewer usable clues, so the evidence leans on US companies.</li>
          <li>The strategy has never been tested through a broad mining downturn.</li>
        </ul>
      </div>
    </details>
  );
}

export function Backtest() {
  const reports = QUARTER_REPORTS;
  const [active, setActive] = useState(Math.max(0, reports.length - 1));

  if (!reports.length) {
    return (
      <div className="page">
        <div className="page-head rise">
          <div className="eyebrow">The scorecard</div>
          <h1>Did the picks actually work?</h1>
        </div>
        <div className="card rise d1">
          <p className="empty-note">
            <strong>No finished quarters loaded.</strong>
            The backend isn't running, or the backtest hasn't been computed yet — nothing is shown
            rather than something made up. Start the backend and reload.
          </p>
        </div>
      </div>
    );
  }

  const r = reports[Math.min(active, reports.length - 1)];
  const win = isWin(r);
  const n = r.actual.filter((a) => a.rank != null).length;

  return (
    <div className="page">
      <div className="page-head rise">
        <div className="eyebrow">The scorecard</div>
        <h1>Did the picks actually work?</h1>
        <p className="page-desc">
          For each past quarter: what we predicted at the time, what the price actually did,
          and how that compares with just buying the market.
        </p>
      </div>

      {/* ① pick a quarter */}
      <div className="rise d1">
        <p className="pick-hint">Choose a quarter</p>
        <QuarterPicker reports={reports} active={active} onPick={setActive} />
      </div>

      {/* ② the call, and the one comparison that matters */}
      <div className="card call-hero section-gap rise d2" style={{ borderLeft: `3px solid var(${win ? "--good" : "--bad"})` }}>
        <div className="split split-call">
          <div>
            <div className="kpi-label" style={{ marginBottom: 8 }}>
              {r.quarter} · {fmtDate(r.windowStart)} – {fmtDate(r.windowEnd)}
            </div>
            <div className="verdict-line">
              We picked <strong style={{ color: "var(--ink)" }}>{r.pick.material}</strong>{" "}
              <span className="tk">{r.pick.etf}</span>. It returned{" "}
              <span className={r.pick.return >= 0 ? "pos" : "neg"}>{pct(r.pick.return)}</span>{" "}
              and finished <strong style={{ color: "var(--ink)" }}>#{r.pick.actualRank ?? "—"} of {n}</strong>.
            </div>
            {r.rating?.prose && (
              <div className="ev-quote" style={{ marginTop: 12 }}>
                {r.rating.prose}
                <span className="src">
                  <AiMark size={13} /> What our AI wrote on {fmtDate(r.decisionDate)} — before any of this had happened
                </span>
              </div>
            )}
            <p className="footnote" style={{ marginTop: 10 }}>
              Real prices from Yahoo Finance, trading costs included. Nothing filed after {fmtDate(r.decisionDate)} was
              used to make the pick.
            </p>
          </div>
          <div>
            <div className="kpi-label" style={{ marginBottom: 10 }}>Against what else you could have done</div>
            <CompareBars
              rows={[
                { label: `${r.pick.material} — our pick`, value: r.pick.return, colorVar: "--c-strategy", emphasis: true },
                { label: "The market (SPY)", value: r.baselines.spy, colorVar: "--c-market" },
                { label: "All six metals", value: r.baselines.eqweight, colorVar: "--c-basket" },
                { label: "Random guess (median)", value: r.baselines.random, colorVar: "--c-random" },
              ]}
              note="Same three months, same $ start. Our pick includes trading costs."
            />
          </div>
        </div>
      </div>

      {/* ③ why the AI picked it — collapsed */}
      <details className="card section-gap disclose rise d3">
        <summary>
          <span>
            <span className="disclose-title">
              <AiMark size={15} /> The filings behind the {r.pick.material.toLowerCase()} call
            </span>
            <span className="disclose-sub">
              {r.evidence.length} filing{r.evidence.length === 1 ? "" : "s"} pushed the score, quotes included
            </span>
          </span>
          <span className="disclose-chev" aria-hidden="true" />
        </summary>
        <div className="disclose-body">
          <Evidence items={r.evidence} material={r.pick.material} />
        </div>
      </details>

      {/* ④ prediction vs reality */}
      <div className="section-gap rise d3">
        <PredVsActual report={r} />
      </div>

      {/* ⑤ the whole run + honest fine print, collapsed */}
      <div className="rise d3">
        <WholeRun quarters={reports.length} />
      </div>
    </div>
  );
}
