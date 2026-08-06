import { useState, type ReactNode } from "react";
import { useTooltip } from "../lib/tooltip";
import { AiMark } from "./ui";

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
  /** true when a language model does the work in this step */
  ai?: boolean;
  flow: [string, string, string]; // mini diagram boxes (middle one accented)
  exampleLabel: string;
  example: ReactNode;
  ruleTag: string;
  rule: ReactNode;
  why: ReactNode;
}

const STAGES: StageDef[] = [
  {
    num: "01",
    title: "Read the filings",
    summary: "Public companies must report to the SEC. We download them.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M3 1.5h7L13 4.5v10H3z" /><path d="M5 7h6M5 9.5h6M5 12h4" opacity={0.6} />
      </svg>
    ),
    flow: ["SEC website", "keep the outlook pages", "clean text"],
    exampleLabel: "For example",
    example: (
      <>
        Freeport-McMoRan files a report on July 23. We pull it, throw away the accounting
        tables, and keep the pages where management talks about the year ahead.
      </>
    ),
    ruleTag: "Keep the useful part",
    rule: (
      <>
        A filing runs hundreds of pages, mostly boilerplate. We keep only the sections about what
        comes next — and if we can't find them, we say so instead of quietly reading everything.
      </>
    ),
    why: (
      <>
        A giant blob of text buries the few sentences that matter. Less in, sharper answer out.
      </>
    ),
  },
  {
    num: "02",
    title: "Find the clues",
    summary: "An AI pulls out every sentence about what happens next.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 8h4l1.5-4 2 8L11 8h3" />
      </svg>
    ),
    ai: true,
    flow: ["Filing text", "AI reads it", "dated clues"],
    exampleLabel: "For example",
    example: (
      <>
        The filing says <em>"we expect copper sales of about 750 million pounds for Q3 2026."</em>{" "}
        That becomes one clue: <strong style={{ color: "var(--ink)" }}>copper · more · July–September 2026</strong>,
        stored with that exact sentence attached.
      </>
    ),
    ruleTag: "Never make things up",
    rule: (
      <>
        Every clue keeps the company's own words attached, so you can check it. If a sentence doesn't
        say <em>when</em> it applies, we drop it rather than guess.
      </>
    ),
    why: (
      <>
        A clue with no dates can't tell one quarter from another. And a quote you can read yourself is
        the difference between a finding and a black box.
      </>
    ),
  },
  {
    num: "03",
    title: "Score each metal",
    summary: "Plain math — no AI — adds the clues up and ranks the six metals.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 13.5V9M6 13.5V5.5M10 13.5V7.5M14 13.5V3" strokeLinecap="square" />
      </svg>
    ),
    flow: ["Clues", "add them up", "1st to 6th"],
    exampleLabel: "For example",
    example: (
      <>
        Good news adds points, bad news subtracts. Recent news counts more than old news. Copper
        ends the quarter on top — so copper is the pick, and we buy the fund that holds copper miners.
      </>
    ),
    ruleTag: "No peeking at the future",
    rule: (
      <>
        A quarter is scored only from filings public before it started. Anything filed later simply
        doesn't exist for that decision — and there's no setting to turn this off.
      </>
    ),
    why: (
      <>
        It's easy to look brilliant when you can see what happened. Blocking that is the only reason
        the results mean anything. The math is also repeatable: run it twice, get the same answer.
      </>
    ),
  },
  {
    num: "04",
    title: "Explain the pick",
    summary: "A second AI writes why the winner won — and can't change the ranking.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2 3h12v8H8l-3 3v-3H2z" />
      </svg>
    ),
    ai: true,
    flow: ["Ranking", "AI writes it up", "the reason"],
    exampleLabel: "For example",
    example: (
      <>
        <em>"Copper ranks first: Freeport guides to higher sales, Teck's new mine is running two
        quarters late, and grid orders are booked into 2027."</em> Every claim points at a real
        filing — including the ones that argue the other way.
      </>
    ),
    ruleTag: "Explains, never decides",
    rule: (
      <>
        Step 3 already fixed the ranking; this AI only describes it. Quote something that isn't in our
        records and the quote is dropped automatically.
      </>
    ),
    why: (
      <>
        It keeps two questions apart: <em>is the signal real?</em> and <em>does the write-up sound
        convincing?</em> A good story shouldn't move the number.
      </>
    ),
  },
  {
    num: "05",
    title: "Check if it worked",
    summary: "Compare the pick to real prices, and to what else you could have done.",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <path d="M2.5 8.5 6 12l7.5-8" />
      </svg>
    ),
    flow: ["Past picks", "real prices", "the verdict"],
    exampleLabel: "For example",
    example: (
      <>
        We replay every past quarter: buy the pick, hold it three months, switch. Then line it up
        against buying the whole market, buying all six metals, and picking at random.
      </>
    ),
    ruleTag: "Four comparisons, always",
    rule: (
      <>
        A return on its own means nothing. We check it against the market (<span className="mono">SPY</span>),
        all six metals equally, and ten thousand{" "}
        <Term def="Pick a metal at random each quarter, ten thousand times over. If our picks can't beat that, we got lucky, not smart.">random guesses</Term>.
      </>
    ),
    why: (
      <>
        "It didn't beat the market, and here's the evidence" is a real result too. Nothing is smoothed
        over.
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
          Click any step to see what it does.
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
              <span className={`ps-icon${s.ai ? " ai" : ""}`}>{s.icon}</span>
              <span className="ps-title">{s.title}</span>
              {s.ai && <span className="ps-ai" title="This step is done by an AI"><AiMark size={14} /></span>}
            </span>
          </button>
        ))}
      </div>

      <div className="pipex-detail">
        <div className="pipex-detail-inner" key={active} aria-live="polite">
          <div>
            <div className="pd-block">
              <div className="pd-label">
                Step {stage.num} · {stage.title}
                {stage.ai && <span className="pd-ai-tag"><AiMark size={12} /> done by AI</span>}
              </div>
              <p className="pd-summary">{stage.summary}</p>
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
              <div className="pd-example">{stage.example}</div>
            </div>
          </div>
          <div>
            <div className="pd-block">
              <div className="pd-label">The rule</div>
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
