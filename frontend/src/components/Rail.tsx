import type { Page } from "../lib/useHashRoute";

interface NavDef {
  id: Page;
  label: string;
  key: string;
  icon: React.ReactNode;
}

const NAV: NavDef[] = [
  { id: "home", label: "Home", key: "1", icon: <path d="M2 7.5 7.5 2.5 13 7.5V13H9.5V9.5h-4V13H2z" /> },
  { id: "forecast", label: "Forecast", key: "2", icon: <><path d="M2 12.5 6 7l3 3 4-6" /><path d="M2 2v11h11" opacity={0.55} /></> },
  { id: "filings", label: "Filings", key: "3", icon: <><path d="M3.5 1.5h5.5L12 4.5v9H3.5z" /><path d="M5.5 6.5h4M5.5 9h4" opacity={0.7} /></> },
  { id: "backtest", label: "Backtest", key: "4", icon: <><path d="M2.5 2v11h10" /><path d="M4.5 10.5v-3M7.5 10.5v-6M10.5 10.5v-4.5" strokeLinecap="square" /></> },
  { id: "statistics", label: "Statistics", key: "5", icon: <><circle cx="7.5" cy="7.5" r="5.5" /><path d="M7.5 2v5.5l3.9 3.9" /></> },
];

export function Rail({ page, navigate }: { page: Page; navigate: (p: Page) => void }) {
  return (
    <aside className="rail">
      <div className="brand">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <path d="M2 18 L8 8 L12 13 L20 3" stroke="var(--accent)" strokeWidth={2.2} strokeLinecap="square" />
          <path d="M2 21 h18" stroke="#6b6553" strokeWidth={1.6} />
        </svg>
        <span className="brand-name">FilingSignal</span>
      </div>

      <nav className="nav" aria-label="Main">
        <div className="nav-label">Research</div>
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
            {n.label}
            <span className="kbd">{n.key}</span>
          </button>
        ))}
      </nav>

      <div className="rail-foot">
        <div><span className="dot-live" />Pipeline healthy</div>
        <div className="mono" style={{ marginTop: 6 }}>point-in-time · v0.9</div>
        <div className="mono">EDGAR sync 06:40 UTC</div>
      </div>
    </aside>
  );
}
