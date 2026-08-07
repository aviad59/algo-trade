import type { Page } from "../lib/useHashRoute";

interface NavDef {
  id: Page;
  label: string;
  /** Phone-tier label. Same meaning, fewer words — four tabs have to share one
      screen width. Hidden above the phone breakpoint, so desktop is untouched. */
  short: string;
  key: string;
  icon: React.ReactNode;
}

const NAV: NavDef[] = [
  { id: "home", label: "How it works", short: "How it works", key: "1", icon: <path d="M2 7.5 7.5 2.5 13 7.5V13H9.5V9.5h-4V13H2z" /> },
  { id: "forecast", label: "This quarter's pick", short: "The pick", key: "2", icon: <><path d="M2 12.5 6 7l3 3 4-6" /><path d="M2 2v11h11" opacity={0.55} /></> },
  { id: "filings", label: "The filings", short: "Filings", key: "3", icon: <><path d="M3.5 1.5h5.5L12 4.5v9H3.5z" /><path d="M5.5 6.5h4M5.5 9h4" opacity={0.7} /></> },
  { id: "backtest", label: "Did it work?", short: "Did it work?", key: "4", icon: <><path d="M2.5 2v11h10" /><path d="M4.5 10.5v-3M7.5 10.5v-6M10.5 10.5v-4.5" strokeLinecap="square" /></> },
];

export function Rail({ page, navigate }: { page: Page; navigate: (p: Page) => void }) {
  return (
    <aside className="rail">
      <div className="brand">
        <svg width="26" height="26" viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <path d="M2 18 L8 8 L12 13 L20 3" stroke="var(--accent)" strokeWidth={2.2} strokeLinecap="square" />
          <path d="M2 21 h18" stroke="var(--ink-3)" strokeWidth={1.6} />
        </svg>
        <span className="brand-name">FilingSignal</span>
      </div>

      <nav className="nav" aria-label="Main">
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`nav-item${page === n.id ? " active" : ""}`}
            onClick={() => navigate(n.id)}
            aria-current={page === n.id ? "page" : undefined}
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth={1.4}>
              {n.icon}
            </svg>
            <span className="nav-text">{n.label}</span>
            <span className="nav-text-short">{n.short}</span>
            <span className="kbd">{n.key}</span>
          </button>
        ))}
      </nav>

      <div className="rail-foot">
        <div>Reads SEC filings, picks one metal ETF each quarter, then checks itself.</div>
      </div>
    </aside>
  );
}
