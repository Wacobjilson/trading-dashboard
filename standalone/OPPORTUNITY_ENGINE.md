# Opportunity Discovery Engine (ODE)

## Purpose
Continuously scan the full liquid US market for statistically interesting
situations where independent evidence aligns — and track every surfaced
candidate to outcome so the scanner itself gets graded. The AI explains and
challenges candidates; **nothing here is a signal** and no LLM generates
candidates.

## How full-market scanning is honest on a free tier
Polygon's **grouped-daily** endpoint returns every US stock's OHLCV in one
call. `market_loop` backfills ~120 trading days (~130 calls at 14s pacing,
~30 min once), then maintains the store with **one call per day**. Liquidity
gate at ingest (price ≥ $5, avg dollar volume ≥ $8M) keeps ~2,000 names in
compact float arrays (`market_bars.json.gz` in the data volume).

## Scoring (fully displayed, deliberately criticizable)
`score = 0.45·technical + 0.10·liquidity + 0.20·agreement + 0.10·sectorStrength
+ 0.05·govContext + 0.10·regimeFit` — weights are display heuristics, shown
on the payload so you can disagree. **Confidence rises only through the
agreement term** (independent strategies flagging the same symbol,
congressional context, sector strength); conflicting evidence (bear regime vs
continuation setups, failed-research strategy families) is listed per item
and subtracts.

## Lifecycle & learning
Every item tracks price path, MFE/MAE, and resolves to confirmed (+8%),
invalidated (below its stated level), or expired (30d). Resolved outcomes
feed per-strategy verdicts (gate 30): *interesting but unproven → candidate
for a pre-registered experiment* / *false-positive-prone* / *needs more
data*. This grades the SCANNER's surfacing quality — it is not a backtest
(no entries, exits, or costs), and any edge claim still requires the
validation pipeline.

## User actions
Watch · promote to watchlist · dismiss · archive · ✨ AI review (opportunity
mode — explains, cites the strategy family's research record, never
recommends). There is deliberately no "accept trade" button.

## Options discovery
Tracked universe only (sector ETFs + SPY via free CBOE delayed chains): IV
rank extremes, short-gamma environments (naive dealer convention, stated),
skew anomalies. Unusual flow, insider activity, analyst revisions, and
institutional ownership have **no free machine-readable source — absent, not
estimated** (DATA_SOURCES.md).

## Known limitations
120-day window (no 200d MA on single stocks — long filters use 100d and say
so); sector mapping covers the curated ticker map (unmapped shown as such);
survivorship-safe going forward (point-in-time store) but the backfill
inherits today's listing universe; single-stock strategy variants are
explicitly staged exploratory even when the sector-ETF version is production.
