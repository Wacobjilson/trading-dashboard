# Catalyst Runner Scanner

Hunts the small-cap "runner" setup: **low float + a volume surge + a fresh news
catalyst**. On the Intel tab (Catalyst runners card) and `/api/runners`.

## Honest framing (read first)
Low-float momentum runners are **the hardest place on this platform to find a
real edge.** The winners look obvious in hindsight, but:
- **survivorship bias** — you only remember the ones that ran;
- **you often can't get filled** at the price you see (gaps, thin books);
- **halts** interrupt exactly the fast moves you'd trade;
- **borrow/locate** costs and availability gate the short side.
So this scanner **surfaces setups and tracks every one forward to outcome** —
it is a *hunting ground / starting watchlist*, **not a validated system**, and
there is deliberately no "backtested edge" claim (the setup can't be cleanly
backtested for the reasons above; the deep-history store is liquid names only).

## How it works
- **Universe / volume** — Polygon grouped-daily (whole US market, already
  fetched daily). Per name, a rolling 25-day (volume, close). Runner-eligible =
  price $1–$50.
- **Trigger** — relative volume ≥ 3× the 20-day average AND a daily move ≥ 6%.
- **Float** — Polygon ticker reference `share_class_shares_outstanding` — a
  **proxy** for true free float (which isn't in free data). Low <50M shares,
  micro <20M.
- **Catalyst** — Finnhub company-news over the last 3 days; fresh headline(s) =
  catalyst flag + count + top headline.
- **Score** = relVol + |move| + low-float bonus (micro +26 / low +13) +
  fresh-catalyst bonus (+22). Setup label from the combination.

## Forward tracking & learning
Every surfaced runner (score ≥ 45) opens a forward track: return / MFE / MAE,
closed after ~7 days. At 20 closed outcomes, a verdict appears — do surfaced
runners actually go up, or is it the hindsight trap? This grades the SCANNER,
not a tradable backtest (no fill assumption).

## Config (`RUNNER_CFG`, tune without touching logic)
minPrice/maxPrice, relVol, movePct, lowFloatShares, microFloatShares, newsDays.

## Rate budget
Enriches only the top ~12 spikers/scan. Shares cached 30 days (rarely change),
news cached 12h, both on the shared Polygon/Finnhub free budgets. Scans every
3h + on each daily market refresh.

## Data gaps (no free feed → not shown, never faked)
True free float, short interest, borrow availability, and halt status. A real
runner playbook needs all four — confirm them on your broker before acting.
