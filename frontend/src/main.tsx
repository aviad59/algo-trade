import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { fetchLiveData } from "./data/api";
import { hydrate } from "./data/fixtures";

// Hydrate fixtures from the live API before the first render, so every chart and
// table shows real backend data with no component changes. If the API is
// unreachable (or VITE_DATA_SOURCE=fixtures), fall back to the demo fixtures.
async function boot() {
  const useApi = (import.meta.env.VITE_DATA_SOURCE ?? "api") !== "fixtures";
  if (useApi) {
    try {
      hydrate(await fetchLiveData());
    } catch (err) {
      console.warn("[FilingSignal] live API unavailable — using demo fixtures.", err);
    }
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

boot();
