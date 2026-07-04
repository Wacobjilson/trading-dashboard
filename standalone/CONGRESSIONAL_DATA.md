# Congressional Data — pipeline reference

## Trade tracker (`congress_loop` → `/api/congress`)
- **Source:** FMP `senate-latest` + `house-latest` (requires `FMP_API_KEY`,
  free tier). Fetched every 6h, 4 pages per chamber.
- **Store:** `congress_trades.json` in the data volume — records accumulate
  beyond FMP's rolling window (capped 8,000 newest), keyed by
  member|date|ticker|side|amount to dedupe.
- **Normalization:** member, chamber, office, trade date, disclosure date,
  computed delay days, ticker, asset description/type, side (buy/sell/other),
  amount band + midpoint, owner, filing link, curated sector mapping, source,
  collection timestamp, verification status.
- **Price enrichment:** the 25 most-disclosed tickers of the last year get 5y
  Yahoo history cached alongside the deep files, enabling performance-since-
  trade, vs-SPY, and vs-sector columns (only where history exists — else "—").
- **Member stats:** trades/buys/sells, median filing delay, 90-day forward
  alpha vs SPY + hit rate, **gated at n≥10 computable trades**.
- **Conviction:** cluster buyers (90d), repeat purchases, size midpoint —
  graded Low/Medium/High/Very High with the point breakdown displayed;
  committee overlap explicitly not scored (no free source).
- **Alerts:** new disclosures on sector-mapped or watchlist tickers push
  through the standard alert engine, with the delay stated inside the alert
  text; deduped by filing id.

## Sector heat
Last-90-day buy/sell counts by mapped sector (by TRADE date), distinct buyers,
top tickers, plus Federal Register document counts per sector. The "read"
column is a plain-language summary (net buying / net selling / balanced).

## Graceful degradation
Without `FMP_API_KEY`, the trades sections display the exact signup path and
everything else on the tab (regulatory feed, political calendar) stays live.
