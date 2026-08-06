/**
 * Global disclaimer, pinned to the bottom of the viewport so it is on screen at
 * all times rather than only after a scroll to the end. Condensed to one line;
 * `.page` reserves matching bottom padding so nothing hides behind it.
 */
export function Footer() {
  return (
    <footer className="site-footer">
      <p>
        <strong>Not investment advice.</strong>
        <span> A student research project — illustrative only, and not a recommendation to buy or sell any
        security. Past performance does not predict future results.</span>
        <span className="site-footer-meta">SEC EDGAR · Yahoo Finance · unaffiliated</span>
      </p>
    </footer>
  );
}
