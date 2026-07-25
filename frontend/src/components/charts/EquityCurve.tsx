import { useRef, useState } from "react";
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

/** Growth of $100: strategy vs four baselines, with hover crosshair. */
export function EquityCurve() {
  const tip = useTooltip();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [crossX, setCrossX] = useState<number | null>(null);

  const W = 980, H = 340, padL = 52, padR = 118, padT = 16, padB = 32;
  const curves: Record<string, number[]> = {};
  for (const s of EQUITY_SERIES) curves[s.key] = cumulative(RETURNS[s.key]);
  const all = Object.values(curves).flat();
  const ymax = Math.max(...all) * 1.04;
  const ymin = Math.min(...all) * 0.92;
  const N = QUARTERS.length + 1;
  const x = (i: number) => padL + (i * (W - padL - padR)) / (N - 1);
  const y = (v: number) => padT + (1 - (v - ymin) / (ymax - ymin)) * (H - padT - padB);

  const yTicks = [100, 150, 200, 250].filter((t) => t <= ymax);
  const startShort = QUARTERS.length ? prevShortQuarter(QUARTERS[0]) : "start";

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
        {EQUITY_SERIES.map((s) => (
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
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Growth of one hundred dollars, strategy versus baselines">
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
          {EQUITY_SERIES.map((s) => {
            const c = curves[s.key];
            const pts = c.map((v, i) => `${x(i)},${y(v)}`).join(" ");
            return (
              <g key={s.key}>
                <polyline
                  points={pts} fill="none" stroke={`var(${s.colorVar})`}
                  strokeWidth={s.emphasis ? 2.6 : 1.8}
                  strokeDasharray={s.dashed ? "5 4" : undefined}
                  strokeLinejoin="round"
                />
                {s.directLabel && (
                  <>
                    <circle cx={x(N - 1)} cy={y(c[c.length - 1])} r={3.5} fill={`var(${s.colorVar})`} stroke="var(--chart-surface)" strokeWidth={2} />
                    <text className="dlabel" x={x(N - 1) + 9} y={y(c[c.length - 1]) + 4}>
                      {s.directLabel} {money(c[c.length - 1])}
                    </text>
                  </>
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
        {EQUITY_SERIES.map((s) => (
          <span className="li" key={s.key}>
            <span className="swatch" style={{ background: `var(${s.colorVar})` }} />{s.label}
          </span>
        ))}
      </div>
    </>
  );
}
