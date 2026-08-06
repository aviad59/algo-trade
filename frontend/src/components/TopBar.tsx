import { DATA_AS_OF, DATA_STATUS, FORECAST_QUARTER } from "../data/fixtures";

/**
 * Persistent context: which quarter the forecast is for and how fresh the data
 * is — point-in-time is the whole claim. When the backend never answered, say
 * exactly that instead of showing nothing at all.
 */
export function TopBar({ title }: { title: string }) {
  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-meta">
        {DATA_STATUS === "offline" ? (
          <span className="chip quiet">no data loaded — the backend isn't running</span>
        ) : (
          <>
            {FORECAST_QUARTER && <span className="chip accent">Forecast {FORECAST_QUARTER}</span>}
            {DATA_AS_OF && <span className="chip">data through {DATA_AS_OF}</span>}
          </>
        )}
      </div>
    </header>
  );
}
