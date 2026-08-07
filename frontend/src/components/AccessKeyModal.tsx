import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AiMark } from "./ui";

/**
 * Asked for on every run, because every run spends the owner's model credits.
 * Prefilled from the last successful key so a repeat run is one click, but the
 * confirmation step is never skipped.
 *
 * Portalled to <body>: this renders from inside a page card, and a fixed
 * element resolves against the nearest transformed ancestor, not the viewport.
 */
export function AccessKeyModal({
  open, initialKey, request, onCancel, onConfirm,
}: {
  open: boolean;
  initialKey: string;
  request: { ticker: string; form: string };
  onCancel: () => void;
  onConfirm: (key: string) => void;
}) {
  const [key, setKey] = useState(initialKey);
  const [err, setErr] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setKey(initialKey);
    setErr(false);
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => { clearTimeout(t); window.removeEventListener("keydown", onKey); };
  }, [open, initialKey, onCancel]);

  if (!open) return null;

  function submit() {
    if (!key.trim()) { setErr(true); inputRef.current?.focus(); return; }
    onConfirm(key.trim());
  }

  return createPortal(
    <>
      <div className="overlay" onClick={onCancel} />
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="akm-title">
        <button className="drawer-close" onClick={onCancel} aria-label="Close">✕</button>

        <div className="eyebrow">One last step</div>
        <h3 id="akm-title">Access key required</h3>

        <p className="modal-lede">
          Our AI is about to read{" "}
          <strong style={{ color: "var(--ink)" }}>{request.ticker || "this company"}'s {request.form}</strong>{" "}
          live from the SEC.
        </p>

        <div className="modal-why">
          <AiMark size={14} />
          <p>
            Reading a new filing calls a paid AI model on the owner's account, so it costs real money.
            The key is their password to stop strangers running up that bill — nothing is charged to you.
          </p>
        </div>

        <label className="f-label" htmlFor="akm-key" style={{ marginBottom: 6 }}>Access key</label>
        <input
          ref={inputRef} id="akm-key" type="password" value={key}
          placeholder="paste the key here"
          className={err ? "input-err" : ""}
          onChange={(e) => { setKey(e.target.value); setErr(false); }}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          style={{ width: "100%" }}
        />
        {err && <p className="modal-err">Enter the key to continue.</p>}
        <p className="footnote" style={{ marginTop: 8 }}>
          Don't have one? Ask whoever shared this project with you.
        </p>

        <div className="modal-actions">
          <button className="btn" onClick={onCancel}>Cancel</button>
          <button className="btn primary" onClick={submit}>Unlock and read</button>
        </div>
      </div>
    </>,
    document.body,
  );
}
