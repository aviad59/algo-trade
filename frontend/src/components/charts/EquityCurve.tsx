import { useEffect, useRef, useState } from "react";
import { EQUITY_SERIES, QUARTERS, RETURNS } from "../../data/fixtures";
import { cumulative, money } from "../../lib/format";
import { useTooltip } from "../../lib/tooltip";

/** "23Q1" -> "22Q4" (the $100 starting point sits one quarter before the first). */
function prevShortQuarter(short: string): string {
  const m = short?.match(/^(\d{2})Q(\d)$/);
  if (!m) return "start";
  let yy = +m[1], q = +m[2] - 1;
  if (q < 1) { q = 4; yy -= 1; }
  return `${String(yy).padStart(2, "0")}Q${q}`;
}

/** Nice y ticks for a dollar range. */
function dollarTicks(ymin: number, ymax: number): number[] {
  const span = ymax - ymin;
  const step = span <= 120 ? 25 : span <= 260 ? 50 : span <= 520 ? 100 : 200;
  const out: number[] = [];
  for (let t = Math.ceil(ymin / step) * step; t <= ymax; t += step) out.push(t);
  return out;
}

/** true while the viewport is in the phone tier (same 640px line as the CSS). */
function usePhone(): boolean {
  const [phone, setPhone] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 640px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const on = () => setPhone(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return phone;
}

/**
 * Growth of $100: our picks vs the market and the other baselines. The one
 * chart the whole project builds to. Baseline lines draw first, then the
 * strategy line separates from the bundle (once; final state under
 * prefers-reduced-motion).
 *
 * The canvas has two geometries. On a phone the SVG scales down to ~330 CSS px,
 * where the desktop 980x340 box would render its axis type at about 4px and
 * reserve a fifth of the width for end-of-line labels; the phone box is nearly
 * square, spends almost nothing on right padding, and drops the end labels in
 * favour of the legend that already sits underneath.
 */
export function EquityCurve() {
  const tip = useTooltip();
  const phone = usePhone();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [crossX, setCrossX] = useState<number | null>(null);
  const [drawn, setDrawn] = useState(false);

  const series = EQUITY_SERIES.filter((s) => Array.isArray(RETURNS[s.key]) && RETURNS[s.key].length > 0);

  // draw-in when the chart first becomes visible (scroll or disclosure open)
  useEffect(() => {
    const el = svgRef.current;
    if (!el || drawn) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setDrawn(true);
    }, { threshold: 0.35 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [drawn]);

  if (!QUARTERS.length || !series.length) {
    return (
      <p className="empty-note">
        <strong>No finished quarters loaded.</strong>
        The growth curve appears once the backend has backtest results to serve.
      </p>
    );
  }

  const [W, H, padL, padR, padT, padB] = phone
    ? [560, 380, 58, 14, 14, 34]
    : [980, 340, 52, 118, 16, 32];
  const curves: Record<string, number[]> = {};
  for (const s of series) curves[s.key] = cumulative(RETURNS[s.key]);
  const all = Object.values(curves).flat();
  const ymax = Math.max(...all) * 1.04;
  const ymin = Math.min(...all) * 0.92;
  const N = QUARTERS.length + 1;
  const x = (i: number) => padL + (i * (W - padL - padR)) / (N - 1);
  const y = (v: number) => padT + (1 - (v - ymin) / (ymax - ymin)) * (H - padT - padB);

  const yTicks = dollarTicks(ymin, ymax);
  const startShort = prevShortQuarter(QUARTERS[0]);

  function onMove(e: React.MouseEvent) {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const sx = (e.clientX - r.left) * (W / r.width);
    const i = Math.max(0, Math.min(N - 1, Math.round((sx - padL) / ((W - padL - padR) / (N - 1)))));
    setCrossX(i);
    const label = i === 0 ? `${startShort.replace("Q", " Q")} (start)` : QUARTERS[i - 1].replace("Q", " Q");
    tip.show(
      <>
        <div className="tt-title">{label}</div>
        {series.map((s) => (
          <div className="tt-row" key={s.key}>
            <span className="tt-sw" style={{ background: `var(${s.colorVar})` }} />
            {s.label}
            <span className="v">{money(curves[s.key][i])}</span>
          </div>
        ))}
      </>,
      e.clientX, e.clientY,
    );
  }
  function onLeave() {
    setCrossX(null);
    tip.hide();
  }

  return (
    <>
      <figure className="chart-box">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Growth of one hundred dollars: our picks versus the market and other baselines">
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
              <text className="axis-t" x={padL - 8} y={y(t) + 3.5} textAnchor="end">${t}</text>
            </g>
          ))}
          {Array.from({ length: Math.ceil(N / 4) }, (_, k) => k * 4).map((i) => (
            <text key={i} className="axis-t" x={x(i)} y={H - 10} textAnchor="middle">
              {i === 0 ? startShort : QUARTERS[i - 1]}
            </text>
          ))}
          <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--axis)" strokeWidth={1} />
          {series.map((s) => {
            const c = curves[s.key];
            const pts = c.map((v, i) => `${x(i)},${y(v)}`).join(" ");
            return (
              <g key={s.key}>
                <polyline
                  className={`curve-line${drawn ? " drawn" : ""}${s.emphasis ? " late" : ""}`}
                  pathLength={1}
                  points={pts} fill="none" stroke={`var(${s.colorVar})`}
                  strokeWidth={s.emphasis ? 2.8 : 1.7}
                  strokeOpacity={s.emphasis ? 1 : 0.8}
                  strokeLinejoin="round"
                />
                {s.directLabel && !phone && (
                  <g className={`curve-end${drawn ? " drawn" : ""}`}>
                    <circle cx={x(N - 1)} cy={y(c[c.length - 1])} r={3.5} fill={`var(${s.colorVar})`} stroke="var(--chart-surface)" strokeWidth={2} />
                    <text className="dlabel" x={x(N - 1) + 9} y={y(c[c.length - 1]) + 4}>
                      {s.directLabel} {money(c[c.length - 1])}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
          {crossX !== null && (
            <line x1={x(crossX)} y1={padT} x2={x(crossX)} y2={H - padB} stroke="var(--axis)" strokeWidth={1} strokeDasharray="3 3" />
          )}
          <rect
            x={padL} y={padT} width={W - padL - padR} height={H - padT - padB}
            fill="transparent" onMouseMove={onMove} onMouseLeave={onLeave}
          />
        </svg>
      </figure>
      <div className="legend">
        {series.map((s) => (
          <span className="li" key={s.key}>
            <span className="swatch" style={{ background: `var(${s.colorVar})` }} />{s.label}
          </span>
        ))}
      </div>
    </>
  );
}
