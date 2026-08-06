import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { fetchLiveData } from "./data/api";
import { hydrate, markLive } from "./data/fixtures";

// Hydrate the data bindings from the read-only API before the first render.
// If the API is unreachable, nothing is invented: every binding stays empty
// and the pages show their empty states.
async function boot() {
  try {
    hydrate(await fetchLiveData());
    markLive();
  } catch (err) {
    console.warn("[FilingSignal] backend unreachable — rendering empty states.", err);
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

boot();
