import { useEffect } from "react";
import { Footer } from "./components/Footer";
import { Rail } from "./components/Rail";
import { TopBar } from "./components/TopBar";
import { FORECAST_QUARTER } from "./data/fixtures";
import { TooltipProvider } from "./lib/tooltip";
import { useHashRoute, type Page } from "./lib/useHashRoute";
import { Backtest } from "./pages/Backtest";
import { Filings } from "./pages/Filings";
import { Forecast } from "./pages/Forecast";
import { Home } from "./pages/Home";
import { Statistics } from "./pages/Statistics";

const KEY_TO_PAGE: Record<string, Page> = {
  "1": "home", "2": "forecast", "3": "filings", "4": "backtest", "5": "statistics",
};

export default function App() {
  const [page, navigate] = useHashRoute();

  // computed at render (after hydration) so the forecast quarter rolls with the data
  const TITLES: Record<Page, string> = {
    home: "Home",
    forecast: `Forecast · ${FORECAST_QUARTER}`,
    filings: "Filings",
    backtest: "Backtest",
    statistics: "Statistics",
  };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const next = KEY_TO_PAGE[e.key];
      if (next) navigate(next);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  return (
    <TooltipProvider>
      <div className="app">
        <Rail page={page} navigate={navigate} />
        <div className="main">
          <TopBar title={TITLES[page]} />
          {page === "home" && <Home />}
          {page === "forecast" && <Forecast />}
          {page === "filings" && <Filings />}
          {page === "backtest" && <Backtest />}
          {page === "statistics" && <Statistics />}
          <Footer />
        </div>
      </div>
    </TooltipProvider>
  );
}
