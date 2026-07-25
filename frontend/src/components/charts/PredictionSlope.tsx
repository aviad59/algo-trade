import { useState } from "react";
import type { QuarterReport } from "../../data/types";
import { pct, signed } from "../../lib/format";

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Optional %-return baselines, drawn on the same left axis as the pick's move. */
const BASELINES: { key: keyof QuarterReport["baselines"]; label: string; color: string; dash: boolean }[] = [
  { key: "spy", label: "SPY", color: "--s2", dash: false },
  { key: "eqweight", label: "Equal-weight", color: "--s3", dash: false },
  { key: "random", label: "Random (median)", color: "--s4", dash: false },
  { key: "hindsight", label: "Hindsight-best", color: "--s5", dash: true },
];

/**
 * Two core slopes from a shared start point for the pick's ETF:
 *   solid copper = the ETF's realized price move (left axis, %)
 *   dashed blue  = our prediction, the conviction z-score (right axis, σ)
 * Plus optional %-return baselines (SPY / eq-weight / random / hindsight) that
 * can be toggled on and off — all sharing the left % axis. Panel tints green
 * when the pick's move agrees in direction with our prediction, red when not.
 */
export function PredictionSlope({ report }: { report: QuarterReport }) {
  const [on, setOn] = useState<Set<string>>(new Set(["prediction"]));
  const toggle = (k: string) =>
    setOn((s) => {
      const next = new Set(s);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });

  const z = report.pick.z;
  const realized = report.pick.realized;

  if (realized == null) {
    return <p className="footnote">No price for {report.pick.etf} this quarter — cannot draw the outcome slope.</p>;
  }

  const W = 640, H = 250, padL = 54, padR = 66, padT = 26, padB = 34;
  const plotH = H - padT - padB;
  const xStart = padL, xEnd = W - padR;

  // left axis (%) must fit the pick plus every enabled baseline
  const activePct = [realized, ...BASELINES.filter((b) => on.has(b.key)).map((b) => report.baselines[b.key])];
  const pmax = Math.max(2, Math.ceil(Math.max(...activePct.map(Math.abs)) / 2) * 2);
  const zmax = Math.max(0.5, Math.ceil(Math.abs(z) * 2) / 2);
  const mapFrac = (f: number) => padT + (1 - (Math.max(-1, Math.min(1, f)) + 1) / 2) * plotH;
  const yPct = (v: number) => mapFrac(v / pmax);
  const yZ = (v: number) => mapFrac(v / zmax);
  const yZero = mapFrac(0);

  const eps = 0.05;
  const agree = Math.abs(z) < eps || Math.abs(realized) < eps ? null : z > 0 === realized > 0;
  const wash = agree == null ? "transparent" : agree ? "var(--good)" : "var(--bad)";

  const cReal = "var(--accent)";   // copper = the real outcome
  const cPred = "var(--s1)";       // blue dashed = our prediction
  const predOn = on.has("prediction");

  return (
    <>
      <figure className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label={`Predicted conviction ${signed(z, 2)} sigma versus realized ${pct(realized)} for ${report.pick.etf}`}>
          <rect x={xStart} y={padT} width={xEnd - xStart} height={plotH} fill={wash} fillOpacity={0.07} />

          <line x1={xStart} y1={yZero} x2={xEnd} y2={yZero} stroke="var(--axis)" strokeWidth={1} />
          <line x1={xStart} y1={padT} x2={xStart} y2={H - padB} stroke="var(--grid)" strokeWidth={1} />
          <line x1={xEnd} y1={padT} x2={xEnd} y2={H - padB} stroke="var(--grid)" strokeWidth={1} />

          {/* left axis (%) */}
          {[pmax, 0, -pmax].map((t) => (
            <text key={`p${t}`} className="axis-t" x={xStart - 8} y={yPct(t) + 3.5} textAnchor="end" fill={cReal}>
              {signed(t, 0)}%
            </text>
          ))}
          {/* right axis (σ) — only when the prediction line is shown */}
          {predOn && [zmax, 0, -zmax].map((t) => (
            <text key={`z${t}`} className="axis-t" x={xEnd + 8} y={yZ(t) + 3.5} textAnchor="start" fill={cPred}>
              {signed(t, 1)}σ
            </text>
          ))}

          <text className="axis-t" x={xStart} y={H - 12} textAnchor="middle">{fmtDate(report.windowStart)}</text>
          <text className="axis-t" x={xEnd} y={H - 12} textAnchor="middle">{fmtDate(report.windowEnd)}</text>

          {/* optional baselines (behind the core lines) */}
          {BASELINES.filter((b) => on.has(b.key)).map((b) => {
            const v = report.baselines[b.key];
            return (
              <g key={b.key}>
                <line x1={xStart} y1={yZero} x2={xEnd} y2={yPct(v)} stroke={`var(${b.color})`} strokeWidth={1.6}
                  strokeDasharray={b.dash ? "5 4" : undefined} strokeLinecap="round" opacity={0.9} />
                <circle cx={xEnd} cy={yPct(v)} r={3} fill={`var(${b.color})`} stroke="var(--chart-surface)" strokeWidth={1.5} />
              </g>
            );
          })}

          {/* prediction slope (dashed) */}
          {predOn && (
            <>
              <line x1={xStart} y1={yZero} x2={xEnd} y2={yZ(z)} stroke={cPred} strokeWidth={2} strokeDasharray="5 4" strokeLinecap="round" />
              <circle cx={xEnd} cy={yZ(z)} r={4} fill={cPred} stroke="var(--chart-surface)" strokeWidth={2} />
            </>
          )}

          {/* realized slope (solid, always on) */}
          <line x1={xStart} y1={yZero} x2={xEnd} y2={yPct(realized)} stroke={cReal} strokeWidth={2.5} strokeLinecap="round" />
          <circle cx={xEnd} cy={yPct(realized)} r={4.5} fill={cReal} stroke="var(--chart-surface)" strokeWidth={2} />

          <circle cx={xStart} cy={yZero} r={3.5} fill="var(--ink-2)" />
        </svg>
      </figure>

      {/* toggles */}
      <div className="slope-toggles">
        <button className={`slope-toggle ${predOn ? "active" : ""}`} onClick={() => toggle("prediction")} aria-pressed={predOn}>
          <span className="st-sw" style={{ background: cPred, borderStyle: "dashed" }} />
          Our prediction <span className="mono">{signed(z, 2)}σ</span>
        </button>
        {BASELINES.map((b) => {
          const active = on.has(b.key);
          const v = report.baselines[b.key];
          return (
            <button key={b.key} className={`slope-toggle ${active ? "active" : ""}`} onClick={() => toggle(b.key)} aria-pressed={active}>
              <span className="st-sw" style={{ background: `var(${b.color})`, borderStyle: b.dash ? "dashed" : "solid" }} />
              {b.label} <span className={`mono ${v >= 0 ? "pos" : "neg"}`}>{pct(v)}</span>
            </button>
          );
        })}
      </div>

      <div className="legend" style={{ justifyContent: "space-between" }}>
        <span className="li">
          <span className="swatch" style={{ background: cReal }} /> {report.pick.etf} actual move
          <strong className={realized >= 0 ? "pos" : "neg"} style={{ marginLeft: 4 }}>{pct(realized)}</strong>
        </span>
        {agree != null && predOn && (
          <span className={`ev-tag ${agree ? "bull" : "bear"}`}>
            {agree ? "✓ direction matched" : "✗ direction missed"}
          </span>
        )}
      </div>
    </>
  );
}
