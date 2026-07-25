import { TREND, TREND_QUARTERS } from "../../data/fixtures";
import { signed } from "../../lib/format";
import { useTooltip } from "../../lib/tooltip";

/** z-score trend for the top-4 materials over the last six quarters. */
export function TrendLines() {
  const tip = useTooltip();
  const W = 860, H = 250, padL = 46, padR = 92, padT = 14, padB = 30;
  const ymin = -0.6, ymax = 1.6;
  const n = TREND_QUARTERS.length;
  const x = (i: number) => padL + (i * (W - padL - padR)) / (n - 1);
  const y = (v: number) => padT + (1 - (v - ymin) / (ymax - ymin)) * (H - padT - padB);
  const ticks = [-0.5, 0, 0.5, 1.0, 1.5];

  return (
    <>
      <figure className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="z-score trend by material over six quarters">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
              <text className="axis-t" x={padL - 8} y={y(t) + 3.5} textAnchor="end">{signed(t, t === 0 ? 0 : 1)}</text>
            </g>
          ))}
          {TREND_QUARTERS.map((q, i) => (
            <text key={q} className="axis-t" x={x(i)} y={H - 10} textAnchor="middle">{q}</text>
          ))}
          {TREND.map((s) => {
            const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
            const last = s.values[s.values.length - 1];
            return (
              <g key={s.material}>
                <polyline points={pts} fill="none" stroke={`var(${s.colorVar})`} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                <circle cx={x(n - 1)} cy={y(last)} r={3.5} fill={`var(${s.colorVar})`} stroke="var(--chart-surface)" strokeWidth={2} />
                <text className="dlabel" x={x(n - 1) + 10} y={y(last) + 4}>{s.material}</text>
                {s.values.map((v, i) => (
                  <circle
                    key={i} cx={x(i)} cy={y(v)} r={9} fill="transparent" className="hoverable"
                    onMouseMove={(e) =>
                      tip.show(
                        <>
                          <div className="tt-title">{s.material} · {TREND_QUARTERS[i]}</div>
                          <div className="tt-row">z-score<span className="v">{signed(v)}</span></div>
                        </>,
                        e.clientX, e.clientY,
                      )
                    }
                    onMouseLeave={tip.hide}
                  />
                ))}
              </g>
            );
          })}
        </svg>
      </figure>
      <div className="legend">
        {TREND.map((s) => (
          <span className="li" key={s.material}>
            <span className="swatch" style={{ background: `var(${s.colorVar})` }} />{s.material}
          </span>
        ))}
      </div>
    </>
  );
}
