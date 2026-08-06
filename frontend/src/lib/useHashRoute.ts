import { useEffect, useState } from "react";

export type Page = "home" | "forecast" | "filings" | "backtest" | "statistics";
const PAGES: Page[] = ["home", "forecast", "filings", "backtest", "statistics"];

function readHash(): Page {
  const raw = window.location.hash.replace(/^#\/?/, "") as Page;
  return PAGES.includes(raw) ? raw : "home";
}

/** Tiny hash router — no dependency, works on any static host. */
export function useHashRoute(): [Page, (p: Page) => void] {
  const [page, setPage] = useState<Page>(readHash);

  useEffect(() => {
    const onChange = () => setPage(readHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = (p: Page) => {
    if (window.location.hash !== `#/${p}`) window.location.hash = `#/${p}`;
    else setPage(p);
    window.scrollTo(0, 0);
  };

  return [page, navigate];
}
