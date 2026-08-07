import { useEffect } from "react";
import { createPortal } from "react-dom";
import type { DatedEffect, Filing } from "../data/types";
import { AiMark, StatusBadge } from "./ui";

function effectTag(e: DatedEffect) {
  // At the miner-ETF target both perspectives share sign: increase = bullish.
  if (e.direction === "increase") return <span className="ev-tag bull">bullish · {e.perspective}</span>;
  return <span className="ev-tag bear">bearish · {e.perspective}</span>;
}

export function FilingDrawer({ filing, onClose }: { filing: Filing; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Portalled to <body>: the demo renders this from inside a page card, where a
  // fixed element would resolve against that card instead of the viewport.
  return createPortal(
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Filing detail: ${filing.company}`}>
        <button className="drawer-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="eyebrow">Filing detail</div>
        <h3>{filing.company} <span className="tk" style={{ color: "var(--accent-ink)" }}>{filing.ticker}</span></h3>

        <div className="kv">
          <span className="k">Form</span><span className="mono" style={{ fontSize: 15 }}>{filing.form}</span>
          <span className="k">Filed</span><span className="mono" style={{ fontSize: 15 }}>{filing.filingDate}</span>
          <span className="k">Materials</span><span>{filing.materials.join(", ")}</span>
          <span className="k">Perspective</span><span style={{ textTransform: "capitalize" }}>{filing.perspective}</span>
          <span className="k">Status</span><span><StatusBadge status={filing.status} /></span>
          <span className="k">Confidence</span><span className="mono" style={{ fontSize: 15 }}>{filing.confidence === null ? "—" : filing.confidence.toFixed(2)}</span>
        </div>

        <hr className="rule" />
        <p className="card-title"><AiMark size={15} /> What our AI made of it</p>
        <p style={{ fontSize: 16, color: "var(--ink-2)", lineHeight: 1.6, marginTop: 4 }}>{filing.summary}</p>

        <hr className="rule" />
        <p className="card-title"><AiMark size={15} /> The clues it found</p>
        {filing.effects.length === 0 ? (
          <p className="footnote" style={{ marginTop: 8 }}>Nothing here was specific enough about dates to count as a clue.</p>
        ) : (
          <div style={{ marginTop: 6 }}>
            {filing.effects.map((e, i) => (
              <div className="effect-row" key={i}>
                <span className="effect-q">
                  {e.window}
                  <span className="effect-meta">{e.magnitude} · {e.direction}</span>
                </span>
                <span>
                  {e.text}
                  <div className="ev-quote" style={{ margin: "6px 0 0" }}>{e.quote}</div>
                </span>
                {effectTag(e)}
              </div>
            ))}
          </div>
        )}

        {filing.warnings.length > 0 && (
          <>
            <hr className="rule" />
            <p className="card-title">Notes from reading it</p>
            <ul className="tight">
              {filing.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          </>
        )}
      </aside>
    </>,
    document.body,
  );
}
