import { QUARTERS, RANK_IC } from "../../data/fixtures";
import { signed } from "../../lib/format";
import { useTooltip } from "../../lib/tooltip";

/** Diverging bars: per-quarter Spearman rank-IC (forecast rank vs realized). */
export function RankICChart() {
  const tip = useTooltip();
  const W = 520, H = 210, padL = 40, padR = 10, padT = 12, padB = 26;
  const ymax = 0.5;
  const n = RANK_IC.length;
  const x = (i: number) => padL + (i * (W - padL - padR)) / n;
  const bw = (W - padL - padR) / n - 2;
  const y0 = padT + (H - padT - padB) / 2;
  const scale = (H - padT - padB) / 2 / ymax;
  const ticks = [0.4, 0.2, -0.2, -0.4];

  return (
    <figure className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Rank information coefficient by quarter">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} y1={y0 - t * scale} x2={W - padR} y2={y0 - t * scale} stroke="var(--grid)" strokeWidth={1} />
            <text className="axis-t" x={padL - 6} y={y0 - t * scale + 3.5} textAnchor="end">{signed(t, 1)}</text>
          </g>
        ))}
        {RANK_IC.map((v, i) => {
          const h = Math.abs(v) * scale;
          const positive = v >= 0;
          const ry = positive ? y0 - h : y0;
          return (
            <rect
              key={i} x={x(i)} y={ry} width={Math.max(bw, 1)} height={Math.max(h, 1)} rx={2}
              fill={`var(${positive ? "--div-pos" : "--div-neg"})`} className="hoverable"
              onMouseMove={(e) =>
                tip.show(
                  <>
                    <div className="tt-title">{QUARTERS[i].replace("Q", " Q")}</div>
                    <div className="tt-row">Rank-IC<span className="v">{signed(v)}</span></div>
                  </>,
                  e.clientX, e.clientY,
                )
              }
              onMouseLeave={tip.hide}
            />
          );
        })}
        <line x1={padL} y1={y0} x2={W - padR} y2={y0} stroke="var(--axis)" strokeWidth={1} />
        {Array.from({ length: Math.ceil(n / 4) }, (_, k) => k * 4).map((i) => (
          <text key={i} className="axis-t" x={x(i) + bw / 2} y={H - 8} textAnchor="middle">{QUARTERS[i]}</text>
        ))}
      </svg>
    </figure>
  );
}
