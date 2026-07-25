import { DATA_AS_OF, FORECAST_QUARTER } from "../data/fixtures";

export function TopBar({ title }: { title: string }) {
  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-meta">
        <span className="chip accent">FORECAST {FORECAST_QUARTER.replace(" ", "·")}</span>
        <span className="chip">AS OF {DATA_AS_OF.toUpperCase()}</span>
      </div>
    </header>
  );
}
