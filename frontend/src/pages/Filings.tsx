import { useMemo, useState } from "react";
import { DigestDemo } from "../components/DigestDemo";
import { FilingDrawer } from "../components/FilingDrawer";
import { Kpi, PerspectivePill, StatusBadge } from "../components/ui";
import { DATA_STATUS, FILINGS, META } from "../data/fixtures";
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

  return (
    <div className="page">
      <div className="page-head rise">
        <div className="eyebrow">The evidence</div>
        <h1>Every report we've read</h1>
        <p className="page-desc">Click any row to see what our AI found inside.</p>
      </div>

      {FILINGS.length > 0 && (
        <div className="grid g4 rise d1">
          <Kpi label="Reports read" value={<span className="mono">{META.filings.toLocaleString()}</span>} note={`${companies} companies · ${materials} metals`} />
          <Kpi label="Clues found" value={<span className="mono">{totalEffects.toLocaleString()}</span>} note={shownNote} />
          <Kpi label="Companies" value={<span className="mono">{companies}</span>} note="miners and buyers" />
          <Kpi label="Avg confidence" value={<span className="mono">{avgConf === null ? "—" : avgConf.toFixed(2)}</span>} note="how sure our AI was" />
        </div>
      )}

      <div className="section-gap rise d2">
        <DigestDemo />
      </div>

      <div className="card section-gap rise d3">
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
                <th>Symbol</th><th>Company</th><th>Type</th><th>Filed</th><th>Metal(s)</th><th>Role</th><th>Status</th><th className="num">Conf.</th><th className="col-view" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-row">
                    {FILINGS.length === 0
                      ? DATA_STATUS === "offline"
                        ? "No filings loaded — the backend isn't running. Start it and reload to browse what the AI has read."
                        : "No filings in the library yet — nothing has been read so far."
                      : "No filings match these filters. Clear a filter to see more."}
                  </td>
                </tr>
              ) : (
                rows.map((f) => (
                  <tr
                    key={f.accession ?? `${f.ticker}|${f.form}|${f.filingDate}`} className="hoverable-row" style={{ cursor: "pointer" }}
                    tabIndex={0} onClick={() => setSelected(f)}
                    onKeyDown={(e) => { if (e.key === "Enter") setSelected(f); }}
                  >
                    <td><span className="tk">{f.ticker}</span></td>
                    <td>{f.company}</td>
                    <td className="mono" style={{ fontSize: 14.5 }}>{f.form}</td>
                    <td className="mono" style={{ fontSize: 14.5, color: "var(--ink-2)" }}>{f.filingDate}</td>
                    <td style={{ fontSize: 15, color: "var(--ink-2)" }}>{f.materials.join(", ")}</td>
                    <td><PerspectivePill perspective={f.perspective} /></td>
                    <td><StatusBadge status={f.status} /></td>
                    <td className="num">{f.confidence === null ? "—" : f.confidence.toFixed(2)}</td>
                    <td className="col-view"><button className="btn sm" onClick={(e) => { e.stopPropagation(); setSelected(f); }}>View</button></td>
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
