import type { ReactNode } from "react";
import type { ExtractionStatus, Perspective } from "../data/types";

/* ---- KPI tile ---- */
export function Kpi({ label, value, unit, note, noteUp }: {
  label: string; value: ReactNode; unit?: string; note?: ReactNode; noteUp?: boolean;
}) {
  return (
    <div className="card kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}{unit && <span className="unit">{unit}</span>}</div>
      {note && <div className={`kpi-note${noteUp ? " up" : ""}`}>{note}</div>}
    </div>
  );
}

/* ---- Card header ---- */
export function CardHead({ title, sub }: { title: string; sub?: string }) {
  return (
    <>
      <p className="card-title">{title}</p>
      {sub && <p className="card-sub">{sub}</p>}
    </>
  );
}

/* ---- Extraction status badge (icon + label — never color alone) ---- */
export function StatusBadge({ status }: { status: ExtractionStatus }) {
  if (status === "Extracted")
    return (
      <span className="status st-ok">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={1.8}><path d="M2 6.5 4.8 9.5 10 3" /></svg>
        Extracted
      </span>
    );
  if (status === "Needs review")
    return (
      <span className="status st-warn">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={1.6}><path d="M6 1.5 11 10.5H1z" /><path d="M6 5v2.4M6 8.8v.2" /></svg>
        Needs review
      </span>
    );
  return (
    <span className="status st-run">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={1.6}><circle cx="6" cy="6" r="4.5" /><path d="M6 3.5V6l1.8 1" /></svg>
      Processing
    </span>
  );
}

/* ---- Perspective pill (producer / consumer) ---- */
export function PerspectivePill({ perspective }: { perspective: Perspective }) {
  return (
    <span className={`pill ${perspective === "producer" ? "persp-p" : "persp-c"}`}>
      {perspective === "producer" ? "Producer" : "Consumer"}
    </span>
  );
}
