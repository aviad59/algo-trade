import type { ReactNode } from "react";
import type { ExtractionStatus, Perspective } from "../data/types";

/* ---- AI mark: a four-point spark. Marks anything a model produced,
        so model output is always visually distinct from computed math. ---- */
export function AiMark({ size = 13, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      className={`ai-mark ${className}`} width={size} height={size} viewBox="0 0 16 16"
      fill="currentColor" aria-hidden="true" focusable="false"
    >
      <path d="M8 0.6 9.5 5.4 14.3 6.9 9.5 8.4 8 13.2 6.5 8.4 1.7 6.9 6.5 5.4z" />
      <path d="M13 10.4 13.7 12.5 15.8 13.2 13.7 13.9 13 16 12.3 13.9 10.2 13.2 12.3 12.5z" opacity={0.65} />
    </svg>
  );
}

/* ---- "AI" tag: the spark plus a label, for section headers ---- */
export function AiTag({ children = "AI" }: { children?: ReactNode }) {
  return (
    <span className="ai-tag">
      <AiMark size={11} />
      {children}
    </span>
  );
}

/* ---- Live badge: pulsing dot for data that is still moving ---- */
export function LiveBadge({ label = "Live" }: { label?: string }) {
  return (
    <span className="live-badge">
      <span className="live-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

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
