import { pct } from "../../lib/format";

export interface CompareRow {
  label: string;
  value: number | null; // % return for the same window
  colorVar: string;     // entity-stable series token
  emphasis?: boolean;   // the pick
}

/**
 * The one comparison that matters, as plain bars: our pick against the market
 * and the other things you could have done, over the same window. All bars
 * share one % scale with a visible zero line; values are always printed, so
 * color never carries the number alone.
 */
export function CompareBars({ rows, note }: { rows: CompareRow[]; note?: string }) {
  const vals = rows.map((r) => r.value).filter((v): v is number => v != null);
  if (!vals.length) {
    return <p className="footnote">No returns to compare for this window yet.</p>;
  }
  const lo = Math.min(0, ...vals);
  const hi = Math.max(0, ...vals);
  const span = hi - lo || 1;
  const zeroPct = ((0 - lo) / span) * 100;

  return (
    <div>
      <div className="cbar" role="img" aria-label={rows.map((r) => `${r.label}: ${r.value == null ? "no data" : pct(r.value)}`).join("; ")}>
        {rows.map((r) => {
          const v = r.value;
          const left = v == null ? zeroPct : ((Math.min(v, 0) - lo) / span) * 100;
          const width = v == null ? 0 : (Math.abs(v) / span) * 100;
          return (
            <div className="cbar-row" key={r.label}>
              <span className={`cbar-name${r.emphasis ? " emph" : ""}`}>
                <span className="swatch sq" style={{ background: `var(${r.colorVar})` }} />
                {r.label}
              </span>
              <span className="cbar-track">
                <span className="cbar-zero" style={{ left: `${zeroPct}%` }} />
                {v != null && (
                  <span
                    className="cbar-fill"
                    style={{ left: `${left}%`, width: `${width}%`, background: `var(${r.colorVar})`, opacity: r.emphasis ? 1 : 0.75 }}
                  />
                )}
              </span>
              <span className={`cbar-val ${v == null ? "" : v >= 0 ? "pos" : "neg"}`}>
                {v == null ? "—" : pct(v)}
              </span>
            </div>
          );
        })}
      </div>
      {note && <p className="cbar-note">{note}</p>}
    </div>
  );
}
