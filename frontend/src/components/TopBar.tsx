import { DATA_AS_OF, DATA_STATUS, FORECAST_QUARTER } from "../data/fixtures";
import { useTheme } from "../lib/theme";

/** Sun in light, moon in dark — the icon shows the theme you are in. */
function ThemeIcon({ dark }: { dark: boolean }) {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.4} aria-hidden="true">
      {dark ? (
        <path d="M13.5 9.7A5.6 5.6 0 0 1 6.3 2.5a5.6 5.6 0 1 0 7.2 7.2z" strokeLinejoin="round" />
      ) : (
        <>
          <circle cx="8" cy="8" r="3.1" />
          <path d="M8 1v1.7M8 13.3V15M1 8h1.7M13.3 8H15M3.05 3.05l1.2 1.2M11.75 11.75l1.2 1.2M12.95 3.05l-1.2 1.2M4.25 11.75l-1.2 1.2" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

/**
 * Persistent context: which quarter the forecast is for and how fresh the data
 * is — point-in-time is the whole claim. When the backend never answered, say
 * exactly that instead of showing nothing at all.
 */
export function TopBar({ title }: { title: string }) {
  const [theme, toggleTheme] = useTheme();
  const dark = theme === "dark";

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
      <button
        className="theme-toggle"
        onClick={toggleTheme}
        aria-label={`Switch to ${dark ? "light" : "dark"} theme`}
        title={`Switch to ${dark ? "light" : "dark"} theme`}
      >
        <ThemeIcon dark={dark} />
        <span className="theme-toggle-text">{dark ? "Dark" : "Light"}</span>
      </button>
    </header>
  );
}
