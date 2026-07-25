export const signed = (v: number, digits = 2): string =>
  `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}`;

export const pct = (v: number, digits = 1): string =>
  `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

export const money = (v: number): string => `$${v.toFixed(0)}`;

/** cumulative growth of $100 through a series of quarterly % returns */
export const cumulative = (returns: number[]): number[] => {
  const out = [100];
  let v = 100;
  for (const r of returns) {
    v *= 1 + r / 100;
    out.push(v);
  }
  return out;
};

/** "26Q3" -> "2026 Q3" */
export const expandQuarter = (q: string): string =>
  q.length === 4 ? `20${q.slice(0, 2)} ${q.slice(2)}` : q;
