import { MATERIALS } from "../../data/fixtures";
import { signed } from "../../lib/format";
import { useTooltip } from "../../lib/tooltip";

/** Diverging horizontal bars: cross-sectional z-score, 0 = quarter average.
    +z (right) = predicted outperformer; the rank-1 pick is emphasized. */
export function ScoreBars({ compact = false }: { compact?: boolean }) {
  const tip = useTooltip();
  const W = 520;
  const rowH = compact ? 34 : 38;
  const padL = 96, padR = 42, padT = 6;
  const H = padT + MATERIALS.length * rowH + 24;

  // Range is padded wider than the data so no bar reaches the name column
  // and the value labels on long negative bars never collide with names.
  const zmax = 2.2, zmin = -2.2;
  const x = (v: number) => padL + ((v - zmin) / (zmax - zmin)) * (W - padL - padR);
  const x0 = x(0);

  const ticks = [-1.5, -0.75, 0, 0.75, 1.5];

  return (
    <figure className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Cross-sectional z-score by material for the forecast quarter">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1={padT} x2={x(t)} y2={H - 22} stroke="var(--grid)" strokeWidth={1} />
            <text className="axis-t" x={x(t)} y={H - 8} textAnchor="middle">{signed(t, t === 0 ? 0 : 1)}</text>
          </g>
        ))}
        {MATERIALS.map((m, i) => {
          const y = padT + i * rowH + (rowH - 18) / 2;
          const top = m.rank === 1;
          const positive = m.z >= 0;
          const fill = top ? "var(--accent)" : positive ? "var(--div-pos)" : "var(--div-neg)";
          const bx = positive ? x0 : x(m.z);
          const bw = Math.abs(x(m.z) - x0);
          const labelX = positive ? x(m.z) + 7 : x(m.z) - 7;
          return (
            <g
              key={m.material}
              className="hoverable"
              onMouseMove={(e) =>
                tip.show(
                  <>
                    <div className="tt-title">{m.material} · {m.etf}</div>
                    <div className="tt-row">z-score<span className="v">{signed(m.z)}</span></div>
                    <div className="tt-row">Producer<span className="v">{m.producerScore.toFixed(2)}</span></div>
                    <div className="tt-row">Consumer<span className="v">{m.consumerScore === null ? "n/a" : m.consumerScore.toFixed(2)}</span></div>
                  </>,
                  e.clientX, e.clientY,
                )
              }
              onMouseLeave={tip.hide}
            >
              <text x={padL - 10} y={y + 13} textAnchor="end" fontSize={12} fontWeight={top ? 650 : 500} fill="var(--ink)" fontFamily="Segoe UI, system-ui, sans-serif">{m.material}</text>
              <rect x={bx} y={y} width={Math.max(bw, 1.5)} height={18} rx={2} fill={fill} />
              <text className="dlabel" x={labelX} y={y + 13} textAnchor={positive ? "start" : "end"} fill={top ? "var(--accent-ink)" : "var(--ink-2)"}>{signed(m.z)}</text>
            </g>
          );
        })}
        <line x1={x0} y1={padT} x2={x0} y2={H - 22} stroke="var(--axis)" strokeWidth={1} />
      </svg>
    </figure>
  );
}
