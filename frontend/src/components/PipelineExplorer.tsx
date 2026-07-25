import { useState, type ReactNode } from "react";
import { useTooltip } from "../lib/tooltip";

/* ---- dotted-underline term with a hover definition ---- */
function Term({ def, children }: { def: string; children: ReactNode }) {
  const tip = useTooltip();
  return (
    <span
      className="term"
      onMouseMove={(e) => tip.show(def, e.clientX, e.clientY)}
      onMouseLeave={tip.hide}
    >
      {children}
    </span>
  );
}

interface StageDef {
  num: string;
  title: string;
  summary: string;
  icon: ReactNode;
  io: { input: string; process: string; output: string };
  flow: [string, string, string]; // mini diagram boxes (middle one accented)
  exampleLabel: string;
  example: string; // mono snippet, \n-separated
  ruleTag: string;
  rule: ReactNode;
  why: ReactNode;
}

const STAGES: StageDef[] = [
  {
    num: "01",
    title: "Ingest filings",
    summary: "Pull six SEC form types from EDGAR and isolate the sections where outlook actually lives.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M3 1.5h7L13 4.5v10H3z" /><path d="M5 7h6M5 9.5h6M5 12h4" opacity={0.6} />
      </svg>
    ),
    io: {
      input: "ticker · form list",
      process: "EDGAR fetch → section isolation",
      output: "FetchedFiling + warnings",
    },
    flow: ["EDGAR", "MD&A / EX-99 isolation", "FetchedFiling"],
    exampleLabel: "Example · FCX 8-K, 2026-07-23",
    example:
`ticker:   FCX      form: 8-K
sections: exhibit  (EX-99.1, earnings release)
          → narrative targeted, tables excluded
warnings: ["exhibit is 409K chars; outlook
           section isolated, not full dump"]`,
    ruleTag: "No silent fallback",
    rule: (
      <>
        For U.S. quarterlies we pull <Term def="Management's Discussion & Analysis — the narrative section of a filing where guidance and outlook live.">MD&A</Term> and
        Risk Factors; for 8-K/6-K the press-release exhibit. If typed section isolation fails and full text is used
        instead, a loud warning is recorded and flows downstream with the extraction.
      </>
    ),
    why: (
      <>
        The predecessor silently fed the extractor a ~10×-diluted full-text blob when section parsing failed
        (Tesla 10-Qs) — and nothing recorded it. Loud inputs keep every extraction comparable and debuggable.
      </>
    ),
  },
  {
    num: "02",
    title: "Extract signals",
    summary: "Agent #1 turns forward-looking sentences into dated, cited, structured effects.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 8h4l1.5-4 2 8L11 8h3" />
      </svg>
    ),
    io: {
      input: "filing sections",
      process: "schema-enforced LLM extraction",
      output: "DatedEffect[] + summary",
    },
    flow: ["Filing text", "Agent #1 · JSON schema", "DatedEffect[]"],
    exampleLabel: "Example · one sentence becomes one effect",
    example:
`"We expect consolidated copper sales of
 approximately 750 million pounds for Q3 2026."
        │
        ▼
material:    copper       perspective: producer
direction:   increase     magnitude:   moderate
window:      2026-07-01 → 2026-09-30
evidence_quote: (verbatim sentence above)`,
    ruleTag: "Drop, don't invent",
    rule: (
      <>
        Every effect carries a <Term def="The effect's producer/consumer tag — inferred per effect from context, since one company can produce one material and consume another.">perspective</Term> tag
        and a verbatim <Term def="The exact filing sentence stored with each effect, so every claim is auditable back to the source.">evidence_quote</Term>.
        Effects whose time window can't be bounded to real dates are dropped and logged — never stretched into a
        vague full-year guess.
      </>
    ),
    why: (
      <>
        A 365-day window can't discriminate quarters — the old pipeline's median window was exactly that, which is
        why its signal blurred. Tight windows plus verbatim quotes are what make the score both sharp and auditable.
      </>
    ),
  },
  {
    num: "03",
    title: "Score materials",
    summary: "Deterministic math aggregates effects into a point-in-time z-score per material.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 13.5V9M6 13.5V5.5M10 13.5V7.5M14 13.5V3" strokeLinecap="square" />
      </svg>
    ),
    io: {
      input: "effects ≤ decision date",
      process: "Σ contributions → breadth gate → z",
      output: "z(material, quarter)",
    },
    flow: ["DatedEffects", "sign·mag·conf·recency·overlap", "z-rank"],
    exampleLabel: "Example · copper, 2026 Q3",
    example:
`contribution = sign · magnitude · confidence
               · recency · overlap
breadth gate: score × (1 − e^(−n_tickers/k))
              one lonely filing can't top the rank

copper 2026Q3:  z = +1.42  → rank 1 of 6`,
    ruleTag: "Point-in-time only",
    rule: (
      <>
        A score for quarter Q admits only effects filed <em>before</em> Q began — there is no
        look-ahead mode to switch off. The <Term def="Cross-sectional standardization: each material's score minus the quarter's mean, divided by its std. High +z = predicted outperformer.">z-score</Term> is
        computed across materials within the quarter, and hyperparameters are never tuned on the test period.
      </>
    ),
    why: (
      <>
        Deterministic math is reproducible and backtestable — an LLM's opinion of its own signal is neither.
        And the <Term def="Consensus weighting: the more distinct companies narrate the same direction, the more the score counts.">breadth gate</Term> encodes
        the thesis: one voice is noise, cross-company agreement is signal.
      </>
    ),
  },
  {
    num: "04",
    title: "Explain the pick",
    summary: "Agent #2 narrates the deterministic rank with cited quotes — it never edits it.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 3h12v8H8l-3 3v-3H2z" />
      </svg>
    ),
    io: {
      input: "z-rank + supporting effects",
      process: "grounded narration, cite-only",
      output: "recommendation + dissent",
    },
    flow: ["z-rank", "Agent #2 · cite-only", "Rationale"],
    exampleLabel: "Example · the copper call, narrated",
    example:
`"Copper ranks #1: FCX guides 750M lbs for Q3
 (8-K 2026-07-23); Teck's QB2 slips two quarters
 (40-F); Eaton's grid backlog runs into 2H27."

dissent: SCCO flags China construction softness
         (10-Q 2026-06-30)`,
    ruleTag: "Explains, never picks",
    rule: (
      <>
        The material→ETF map is frozen config and the rank is the scorer's output — Agent #2 touches neither.
        Every claim must cite a quote that exists in the buffer; unknown citations are dropped by code.
      </>
    ),
    why: (
      <>
        This separates "is the signal real?" from "did the model talk a good game?". The rated number stays
        reproducible and backtestable, while the UI still gets a human "why" — with the dissent shown, not hidden.
      </>
    ),
  },
  {
    num: "05",
    title: "Evaluate honestly",
    summary: "A look-ahead-free backtest measures the pick against four baselines.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2.5 8.5 6 12l7.5-8" />
      </svg>
    ),
    io: {
      input: "28 quarters of picks",
      process: "top-1 rotation · costs",
      output: "verdict + tearsheet",
    },
    flow: ["Quarterly picks", "rotation vs 4 baselines", "Verdict"],
    exampleLabel: "Example · the verdict, 2019 Q3 – 2026 Q2",
    example:
`vs SPY           +3.1%/yr    beat
vs eq-weight     +4.5%/yr    beat
vs random (MC)   +6.8%/yr    beat
vs hindsight     −9.3%/yr    trails

rank-IC 0.19 · permutation p = 0.04`,
    ruleTag: "Four baselines or it didn't happen",
    rule: (
      <>
        SPY, equal-weight materials, a 10k-run <Term def="Random-pick Monte Carlo: pick a random material each quarter, 10,000 times — the luck floor any real signal must clear.">random-pick null</Term>,
        and the hindsight-best ceiling — plus a <Term def="Shuffle the material labels 10,000× and recompute mean rank-IC to ask: could this correlation be luck?">permutation test</Term> on
        the quarterly <Term def="Spearman correlation between forecast rank and realized next-quarter return rank — did higher scores actually mean higher returns?">rank-IC</Term>.
      </>
    ),
    why: (
      <>
        A pick means nothing without its baselines. "The signal does not beat hold, and here is the
        look-ahead-free, cost-adjusted evidence" is a valid success — honesty is the differentiator.
      </>
    ),
  },
];

export function PipelineExplorer() {
  const [active, setActive] = useState(0);
  const [pinned, setPinned] = useState(false);

  /* Hover previews a stage; click pins it. Starts at stage 01, deterministic. */
  const preview = (i: number) => { if (!pinned) setActive(i); };

  const stage = STAGES[active];
  /* badge centers sit at 10%, 30%, 50%, 70%, 90% of the rail */
  const fillPct = 10 + active * 20;

  return (
    <div>
      <div className="pipex-head">
        <p className="card-title">The pipeline</p>
        <p className="card-sub" style={{ marginBottom: 0 }}>
          Five stages from raw filing to honest verdict. Hover a stage for its input → output; click it to pin the
          detail below. Every forecast is reproducible from the filings that existed on the day it was made.
        </p>
      </div>

      <div className="pipex-rail" aria-hidden="true">
        <div className="rail-line" />
        <div className="rail-fill" style={{ width: `${fillPct}%` }} />
        {[20, 40, 60, 80].map((pos, i) => (
          <span
            key={pos}
            className={`rail-chev${pos < fillPct ? " lit" : ""}`}
            style={{ left: `${pos}%`, animationDelay: `${i * 0.22}s` }}
          >
            ››
          </span>
        ))}
        <div className="pipex-badges">
          {STAGES.map((s, i) => (
            <span key={s.num} className={`pipex-badge${i === active ? " active" : i < active ? " done" : ""}`}>
              {s.num}
            </span>
          ))}
        </div>
      </div>

      <div className="pipex-stages">
        {STAGES.map((s, i) => (
          <button
            key={s.num}
            className={`pipex-stage${i === active ? " active" : ""}`}
            onMouseEnter={() => preview(i)}
            onFocus={() => preview(i)}
            onClick={() => {
              if (pinned && i === active) setPinned(false);
              else { setPinned(true); setActive(i); }
            }}
            aria-pressed={i === active}
          >
            <span className="ps-top">
              <span className="ps-icon">{s.icon}</span>
              <span className="ps-title">{s.title}</span>
            </span>
            <span className="ps-sum">{s.summary}</span>
            <span className="ps-io">
              <span>
                <span className="ps-io-inner">
                  <span className="ps-io-row"><span className="k">IN</span><span className="v">{s.io.input}</span></span>
                  <span className="ps-io-row"><span className="k">RUN</span><span className="v">{s.io.process}</span></span>
                  <span className="ps-io-row"><span className="k">OUT</span><span className="v">{s.io.output}</span></span>
                </span>
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="pipex-detail">
        <div className="pipex-detail-inner" key={active} aria-live="polite">
          <div>
            <div className="pd-block">
              <div className="pd-label">Stage {stage.num} · {stage.title}</div>
              <div className="mini-flow">
                <span className="mf-box">{stage.flow[0]}</span>
                <span className="mf-arrow">→</span>
                <span className="mf-box accent">{stage.flow[1]}</span>
                <span className="mf-arrow">→</span>
                <span className="mf-box">{stage.flow[2]}</span>
              </div>
            </div>
            <div className="pd-block">
              <div className="pd-label">{stage.exampleLabel}</div>
              <pre className="snippet">{stage.example}</pre>
            </div>
          </div>
          <div>
            <div className="pd-block">
              <div className="pd-label">Key rule</div>
              <span className="rule-tag">{stage.ruleTag}</span>
              <div className="pd-rule-text">{stage.rule}</div>
            </div>
            <div className="pd-block">
              <div className="pd-label">Why it matters</div>
              <div className="pd-why">{stage.why}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
