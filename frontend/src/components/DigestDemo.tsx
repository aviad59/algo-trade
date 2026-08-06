import { useState } from "react";
import { digestFiling } from "../data/api";
import type { Filing } from "../data/types";
import { AccessKeyModal } from "./AccessKeyModal";
import { FilingDrawer } from "./FilingDrawer";
import { ThinkingBar } from "./ThinkingBar";
import { AiMark } from "./ui";

const FORMS = ["10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"];
/** Plain-English name for each SEC form, so the picker isn't just codes. */
const FORM_NAMES: Record<string, string> = {
  "10-K": "annual report",
  "10-Q": "quarterly report",
  "8-K": "news / press release",
  "20-F": "annual report (foreign)",
  "40-F": "annual report (Canada)",
  "6-K": "update (foreign)",
};

/**
 * The live reviewer demo: pick a company + form, the backend fetches that one
 * filing from the SEC and runs the extractor on it in real time. Access-key
 * gated so the baked-in model key can't be abused.
 */
export function DigestDemo() {
  const [dTicker, setDTicker] = useState("");
  const [dForm, setDForm] = useState("8-K");
  const [dBefore, setDBefore] = useState("");
  const [dKey, setDKey] = useState(() => (typeof localStorage !== "undefined" ? localStorage.getItem("fs_api_key") ?? "" : ""));
  const [dBusy, setDBusy] = useState(false);
  const [dMsg, setDMsg] = useState<{ kind: "info" | "ok" | "warn" | "err"; text: string } | null>(null);
  const [keyModal, setKeyModal] = useState(false);
  const [result, setResult] = useState<Filing | null>(null);

  /** Step 1: validate what we can locally, then always confirm the key. */
  function requestDigest() {
    if (!dTicker.trim()) { setDMsg({ kind: "err", text: "Enter a company symbol first — try FCX." }); return; }
    setDMsg(null);
    setKeyModal(true);
  }

  /** Step 2: key confirmed in the modal — actually spend the model. */
  async function digest(apiKey: string) {
    const t = dTicker.trim().toUpperCase();
    setKeyModal(false);
    setDKey(apiKey);
    try { localStorage.setItem("fs_api_key", apiKey); } catch { /* ignore */ }
    setDBusy(true);
    setDMsg(null);
    try {
      const res = await digestFiling({ ticker: t, form: dForm, before: dBefore, apiKey });
      if (res.status === "extracted" || res.status === "cached") {
        setResult(res.filing);
        const n = res.filing.effects.length;
        setDMsg({ kind: "ok", text: `${res.status === "cached" ? "Already read this one" : "Done"} — ${res.filing.ticker} ${res.filing.form} (${res.filing.filingDate}), ${n} clue${n === 1 ? "" : "s"} found. Opened below.` });
      } else if (res.status === "filtered") {
        setDMsg({ kind: "warn", text: `Skipped before the AI ran, so nothing was spent: ${res.reason}` });
      } else if (res.status === "not_found") {
        setDMsg({ kind: "warn", text: res.reason });
      } else {
        setDMsg({ kind: "err", text: res.reason || "unknown error" });
      }
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      setDMsg({ kind: "err", text: /401|invalid|key/i.test(m) ? "Invalid or missing access key." : m });
    } finally {
      setDBusy(false);
    }
  }

  return (
    <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
      <p className="card-title"><AiMark size={15} /> Try it yourself — watch our AI read a filing</p>
      <p className="card-sub">Pick a company and a report type. We fetch it from the SEC and read it live, right now.</p>

      <div className="digest-form">
        <div className="df-field">
          <label className="f-label" htmlFor="d-ticker">1 · Company</label>
          <input id="d-ticker" type="text" placeholder="FCX" value={dTicker} onChange={(e) => setDTicker(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !dBusy) requestDigest(); }} />
          <span className="df-hint">Try FCX, TECK or ETN</span>
        </div>
        <div className="df-field">
          <label className="f-label" htmlFor="d-form">2 · Report type</label>
          <select id="d-form" value={dForm} onChange={(e) => setDForm(e.target.value)}>
            {FORMS.map((f) => <option key={f} value={f}>{f} — {FORM_NAMES[f]}</option>)}
          </select>
          <span className="df-hint">8-K is the quickest</span>
        </div>
        <div className="df-field">
          <label className="f-label" htmlFor="d-before">3 · Filed before <span className="df-opt">optional</span></label>
          <input id="d-before" type="date" value={dBefore} onChange={(e) => setDBefore(e.target.value)} />
          <span className="df-hint">Empty = most recent</span>
        </div>
        <div className="df-field df-go">
          <button className="btn primary" onClick={requestDigest} disabled={dBusy}>
            {dBusy ? "Reading…" : "Read this filing"}
          </button>
          <span className="df-hint">Needs an access key</span>
        </div>
      </div>

      {dBusy && <ThinkingBar ticker={dTicker.trim().toUpperCase()} form={dForm} />}

      {!dBusy && dMsg && (
        <p className="footnote" style={{ marginTop: 14, color: dMsg.kind === "err" ? "var(--bad-text)" : dMsg.kind === "ok" ? "var(--good-text)" : dMsg.kind === "warn" ? "var(--warn)" : "var(--ink-2)" }}>
          {dMsg.text}
        </p>
      )}

      <AccessKeyModal
        open={keyModal}
        initialKey={dKey}
        request={{ ticker: dTicker.trim().toUpperCase(), form: dForm }}
        onCancel={() => setKeyModal(false)}
        onConfirm={digest}
      />

      {result && <FilingDrawer filing={result} onClose={() => setResult(null)} />}
    </div>
  );
}
