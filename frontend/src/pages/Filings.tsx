import { useMemo, useState } from "react";
import { FilingDrawer } from "../components/FilingDrawer";
import { Kpi, PerspectivePill, StatusBadge } from "../components/ui";
import { digestFiling } from "../data/api";
import { FILINGS, META } from "../data/fixtures";
import type { Filing } from "../data/types";

const FORMS = ["10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"];
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

  async function digest() {
    const t = dTicker.trim().toUpperCase();
    if (!t) { setDMsg({ kind: "err", text: "Enter a ticker." }); return; }
    if (!dKey.trim()) { setDMsg({ kind: "err", text: "Enter the access key (ask the app owner)." }); return; }
    try { localStorage.setItem("fs_api_key", dKey.trim()); } catch { /* ignore */ }
    setDBusy(true);
    setDMsg({ kind: "info", text: `Fetching the ${dForm} for ${t}${dBefore ? ` on/before ${dBefore}` : " (latest)"} and running Agent #1…` });
    try {
      const res = await digestFiling({ ticker: t, form: dForm, before: dBefore, apiKey: dKey.trim() });
      if (res.status === "extracted" || res.status === "cached") {
        setSelected(res.filing);
        const n = res.filing.effects.length;
        setDMsg({ kind: "ok", text: `${res.status === "cached" ? "Already digested" : "Digested"} ${res.filing.ticker} ${res.filing.form} (${res.filing.filingDate}) — ${n} effect${n === 1 ? "" : "s"}. Opened below.` });
      } else if (res.status === "filtered") {
        setDMsg({ kind: "warn", text: `Filtered before the LLM (no tokens spent): ${res.reason}` });
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
        <div className="eyebrow">Ingestion · control room</div>
        <h1>Filings</h1>
        <p className="page-desc">
          Every document the engine has digested, with extraction status, perspective tag, and confidence. Click any
          row for the structured, dated effects pulled from that filing.
        </p>
      </div>

      <div className="grid g4">
        <Kpi label="Filings digested" value={<span className="mono">{META.filings.toLocaleString()}</span>} note={`${companies} companies · ${materials} materials`} />
        <Kpi label="Extractions" value={<span className="mono">{META.extractions.toLocaleString()}</span>} note="one per (filing × model)" />
        <Kpi label="Extracted effects" value={<span className="mono">{totalEffects.toLocaleString()}</span>} note={shownNote} />
        <Kpi label="Avg confidence" value={<span className="mono">{avgConf === null ? "—" : avgConf.toFixed(2)}</span>} note={`over ${withConf} shown`} />
      </div>

      <div className="card section-gap" style={{ borderLeft: "3px solid var(--accent)" }}>
        <p className="card-title">Digest a filing — live pipeline</p>
        <p className="card-sub">
          Pick a ticker, form, and date. We fetch the most-recent <span className="mono">{dForm}</span> filed on or before
          that date from EDGAR, run <strong style={{ color: "var(--ink)" }}>Agent #1</strong> live, and show the summary +
          dated effects. Already-digested filings are returned free. Access-key protected — it spends the model.
        </p>
        <div className="filter-row" style={{ marginBottom: 0, alignItems: "flex-end" }}>
          <div>
            <label className="f-label" htmlFor="d-ticker">Ticker</label>
            <input id="d-ticker" type="text" placeholder="e.g. FCX" value={dTicker} onChange={(e) => setDTicker(e.target.value)} style={{ width: 110 }} onKeyDown={(e) => { if (e.key === "Enter" && !dBusy) digest(); }} />
          </div>
          <div>
            <label className="f-label" htmlFor="d-form">Form</label>
            <select id="d-form" value={dForm} onChange={(e) => setDForm(e.target.value)}>
              {FORMS.map((f) => <option key={f}>{f}</option>)}
            </select>
          </div>
          <div>
            <label className="f-label" htmlFor="d-before">On or before</label>
            <input id="d-before" type="date" value={dBefore} onChange={(e) => setDBefore(e.target.value)} />
          </div>
          <div>
            <label className="f-label" htmlFor="d-key">Access key</label>
            <input id="d-key" type="password" placeholder="key" value={dKey} onChange={(e) => setDKey(e.target.value)} style={{ width: 130 }} onKeyDown={(e) => { if (e.key === "Enter" && !dBusy) digest(); }} />
          </div>
          <div><button className="btn primary" onClick={digest} disabled={dBusy}>{dBusy ? "Digesting…" : "Digest filing"}</button></div>
        </div>
        {dMsg && (
          <p className="footnote" style={{ marginTop: 12, color: dMsg.kind === "err" ? "var(--bad-text)" : dMsg.kind === "ok" ? "var(--good-text)" : dMsg.kind === "warn" ? "var(--warn)" : "var(--ink-2)" }}>
            {dBusy ? "⏳ " : ""}{dMsg.text}
          </p>
        )}
      </div>

      <div className="card section-gap">
        <p className="card-title">Digested filings</p>
        <p className="card-sub">Search by ticker or company; filter by material, form, or status.</p>
        <div className="filter-row">
          <div>
            <label className="f-label" htmlFor="f-search">Search</label>
            <input id="f-search" type="text" placeholder="Ticker or company…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div>
            <label className="f-label" htmlFor="f-material">Material</label>
            <select id="f-material" value={material} onChange={(e) => setMaterial(e.target.value)}>
              <option value="">All materials</option>
              {MATERIAL_OPTS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="f-label" htmlFor="f-form">Form</label>
            <select id="f-form" value={form} onChange={(e) => setForm(e.target.value)}>
              <option value="">All forms</option>
              {FORMS.map((f) => <option key={f}>{f}</option>)}
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
                <th>Ticker</th><th>Company</th><th>Form</th><th>Filed</th><th>Material(s)</th><th>Persp.</th><th>Status</th><th className="num">Conf.</th><th />
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
