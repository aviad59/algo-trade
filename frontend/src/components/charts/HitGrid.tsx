import { HITGRID_MATERIALS, HITS, PICKS, QUARTERS } from "../../data/fixtures";
import { useTooltip } from "../../lib/tooltip";

/** Last 12 quarters × 6 materials. Filled = beat the basket; outlined = the pick. */
export function HitGrid() {
  const tip = useTooltip();
  const quarters = QUARTERS.slice(-12);

  return (
    <div className="hitgrid" style={{ gridTemplateColumns: `92px repeat(${quarters.length}, 1fr)` }}>
      <div className="hg-lab rowlab" />
      {quarters.map((q) => (
        <div className="hg-lab" key={q}>{q}</div>
      ))}
      {HITGRID_MATERIALS.map((m, mi) => (
        <div className="hg-row-group" key={m} style={{ display: "contents" }}>
          <div className="hg-lab rowlab">{m}</div>
          {quarters.map((q, qi) => {
            const hit = HITS[qi][mi] === 1;
            const rec = PICKS[qi] === mi;
            return (
              <div
                key={q}
                className={`hg-cell${hit ? " hit" : ""}${rec ? " rec" : ""} hoverable`}
                onMouseMove={(e) =>
                  tip.show(
                    <>
                      <div className="tt-title">{m} · {q}</div>
                      <div className="tt-row">{hit ? "Beat basket" : "Trailed basket"}{rec ? " · pick" : ""}</div>
                    </>,
                    e.clientX, e.clientY,
                  )
                }
                onMouseLeave={tip.hide}
              >
                {hit ? "✓" : "·"}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
