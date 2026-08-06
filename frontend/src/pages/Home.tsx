import { PipelineExplorer } from "../components/PipelineExplorer";

export function Home() {
  return (
    <div className="page">
      <div className="page-head">
        <div className="eyebrow">How it works</div>
        <h1>We read what mining companies tell the SEC — then guess which metal does best next.</h1>
        <p className="page-desc">
          Every quarter we pick one metal out of six, then check whether we were right.
        </p>
      </div>

      <div className="section-gap">
        <PipelineExplorer />
      </div>
    </div>
  );
}
