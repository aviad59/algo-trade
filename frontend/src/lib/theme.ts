import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "fs_theme";

/** Whatever index.html's boot script already put on <html>. Dark by default. */
function current(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

/**
 * Reader-chosen theme, persisted. The OS setting is deliberately not consulted:
 * this dashboard has one intended look, and the reader overrides it explicitly
 * or not at all. The <html data-theme> attribute is the single source of truth
 * — the boot script sets it before first paint so there is no light flash, and
 * this hook only ever moves it from one value to the other.
 */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch { /* private mode — session only */ }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return [theme, toggle];
}
