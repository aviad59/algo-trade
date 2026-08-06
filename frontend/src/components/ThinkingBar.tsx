import { useEffect, useState } from "react";
import { AiMark } from "./ui";

/**
 * Progress for the live digest. The backend is a single request with no
 * streaming, so the stages advance on a timer — they name the real work in
 * order, but the timing is indicative, not measured. The bar itself is
 * indeterminate, so it never claims a percentage it doesn't know.
 */
const STAGES = [
  { at: 0, label: "Looking up the filing on SEC EDGAR" },
  { at: 2500, label: "Downloading the document" },
  { at: 6000, label: "Finding the pages about the future" },
  { at: 10000, label: "Our AI is reading it" },
  { at: 18000, label: "Pulling out the dated clues" },
  { at: 27000, label: "Almost there — long filings take a minute" },
];

export function ThinkingBar({ ticker, form }: { ticker: string; form: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    setStep(0);
    const timers = STAGES.slice(1).map((s, i) => setTimeout(() => setStep(i + 1), s.at));
    return () => timers.forEach(clearTimeout);
  }, [ticker, form]);

  return (
    <div className="thinking" role="status" aria-live="polite">
      <div className="thinking-head">
        <AiMark size={14} className="spin-soft" />
        <span className="thinking-label">{STAGES[step].label}</span>
        <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
      </div>

      <div className="thinking-track"><div className="thinking-fill" /></div>

      <div className="thinking-steps">
        {STAGES.slice(0, 5).map((s, i) => (
          <span key={s.label} className={`thinking-step${i < step ? " done" : i === step ? " now" : ""}`} />
        ))}
      </div>

      <p className="thinking-note">
        Reading {ticker} {form} · usually 10–40 seconds. The result is saved either way.
      </p>
    </div>
  );
}
