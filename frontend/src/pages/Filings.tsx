import { useMemo, useState } from "react";
import { AccessKeyModal } from "../components/AccessKeyModal";
import { FilingDrawer } from "../components/FilingDrawer";
import { ThinkingBar } from "../components/ThinkingBar";
import { AiMark, Kpi, PerspectivePill, StatusBadge } from "../components/ui";
import { digestFiling } from "../data/api";
import { FILINGS, META } from "../data/fixtures";
import type { Filing } from "../data/types";

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
const MATERIAL_OPTS = ["Copper", "Gold", "Uranium", "Silver", "Steel", "Rare Earths"];
const STATUS_OPTS = ["Extracted", "Needs review", "Processing"];

export function Filings() {
  const [search, setSearch] = useState("");
  const [material, setMaterial] = useState("");
  const [form, setForm] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Filing | null>(null);

  // live one-filing digest (reviewer demo)
  const [dTicker, setDTicker] = useState("");
  const [dForm, setDForm] = useState("8-K");
  const [dBefore, setDBefore] = useState("");
  const [dKey, setDKey] = useState(() => (typeof localStorage !== "undefined" ? localStorage.getItem("fs_api_key") ?? "" : ""));
  const [dBusy, setDBusy] = useState(false);
  const [dMsg, setDMsg] = useState<{ kind: "info" | "ok" | "warn" | "err"; text: string } | null>(null);
  const [keyModal, setKeyModal] = useState(false);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return FILINGS.filter(
      (f) =>
        (!q || f.ticker.toLowerCase().includes(q) || f.company.toLowerCase().includes(q)) &&
        (!material || f.materials.includes(material)) &&
        (!form || f.form === form) &&
        (!status || f.status === status),
    );
  }, [search, material, form, status]);

  // KPI aggregates. META.filings/extractions are buffer-wide (real totals);
  // effect/confidence stats are over the filings the /filings endpoint returned.
  const companies = useMemo(() => new Set(FILINGS.map((f) => f.ticker)).size, []);
  const materials = useMemo(() => new Set(FILINGS.flatMap((f) => f.materials)).size, []);
  const totalEffects = useMemo(() => FILINGS.reduce((s, f) => s + f.effects.length, 0), []);
  const confVals = useMemo(() => FILINGS.map((f) => f.confidence).filter((c): c is number => c !== null), []);
  const withConf = confVals.length;
  const avgConf = withConf ? confVals.reduce((a, b) => a + b, 0) / withConf : null;
  const shownNote = `in ${FILINGS.length.toLocaleString()} shown`;

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
        setSelected(res.filing);
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
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">Step 1 &amp; 2 — the reading</div>
        <h1>Every report we've read</h1>
        <p className="page-desc">Click any row to see what our AI found inside.</p>
      </div>

      <div className="grid g4">
        <Kpi label="Reports read" value={<span className="mono">{META.filings.toLocaleString()}</span>} note={`${companies} companies · ${materials} metals`} />
        <Kpi label="Clues found" value={<span className="mono">{totalEffects.toLocaleString()}</span>} note={shownNote} />
        <Kpi label="Companies" value={<span className="mono">{companies}</span>} note="miners and buyers" />
        <Kpi label="Avg confidence" value={<span className="mono">{avgConf === null ? "—" : avgConf.toFixed(2)}</span>} note="how sure our AI was" />
      </div>

      <div className="card section-gap" style={{ borderLeft: "3px solid var(--accent)" }}>
        <p className="card-title"><AiMark size={13} /> Try it yourself — watch our AI read a filing</p>
        <p className="card-sub">We fetch it from the SEC and read it live.</p>

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
      </div>

      <AccessKeyModal
        open={keyModal}
        initialKey={dKey}
        request={{ ticker: dTicker.trim().toUpperCase(), form: dForm }}
        onCancel={() => setKeyModal(false)}
        onConfirm={digest}
      />

      <div className="card section-gap">
        <p className="card-title">All reports</p>
        <p className="card-sub">Search or filter below.</p>
        <div className="filter-row">
          <div>
            <label className="f-label" htmlFor="f-search">Search</label>
            <input id="f-search" type="text" placeholder="Ticker or company…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div>
            <label className="f-label" htmlFor="f-material">Metal</label>
            <select id="f-material" value={material} onChange={(e) => setMaterial(e.target.value)}>
              <option value="">All metals</option>
              {MATERIAL_OPTS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="f-label" htmlFor="f-form">Report type</label>
            <select id="f-form" value={form} onChange={(e) => setForm(e.target.value)}>
              <option value="">All types</option>
              {FORMS.map((f) => <option key={f} value={f}>{f} — {FORM_NAMES[f]}</option>)}
            </select>
          </div>
          <div>
            <label className="f-label" htmlFor="f-status">Status</label>
            <select id="f-status" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              {STATUS_OPTS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <span className="count-note">{rows.length} of {FILINGS.length} shown</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th><th>Company</th><th>Type</th><th>Filed</th><th>Metal(s)</th><th>Role</th><th>Status</th><th className="num">Conf.</th><th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={9} className="empty-row">No filings match these filters.</td></tr>
              ) : (
                rows.map((f) => (
                  <tr
                    key={f.accession ?? `${f.ticker}|${f.form}|${f.filingDate}`} className="hoverable-row" style={{ cursor: "pointer" }}
                    tabIndex={0} onClick={() => setSelected(f)}
                    onKeyDown={(e) => { if (e.key === "Enter") setSelected(f); }}
                  >
                    <td><span className="tk">{f.ticker}</span></td>
                    <td>{f.company}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{f.form}</td>
                    <td className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{f.filingDate}</td>
                    <td style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{f.materials.join(", ")}</td>
                    <td><PerspectivePill perspective={f.perspective} /></td>
                    <td><StatusBadge status={f.status} /></td>
                    <td className="num">{f.confidence === null ? "—" : f.confidence.toFixed(2)}</td>
                    <td><button className="btn sm" onClick={(e) => { e.stopPropagation(); setSelected(f); }}>View</button></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <FilingDrawer filing={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
