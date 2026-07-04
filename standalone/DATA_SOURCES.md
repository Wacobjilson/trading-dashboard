# Data Sources — complete registry

Every source, its refresh interval, and known limitations. Rule: a metric that
cannot be derived from a listed source is displayed as unavailable, never
estimated.

| Source | Auth | Used for | Refresh | Limitations |
|---|---|---|---|---|
| Polygon (free tier) | key | live daily + 15-min bars (signal paths) | daily bars 6h, 5 req/min pacing | 2yr window; 15-min delayed |
| Yahoo v8 chart | none | deep research history (~25y adjusted) | 7-day cache | unofficial endpoint — could break (Tiingo fallback exists); adjusted-close methodology unverified beyond Polygon-overlap check |
| **Tiingo** (added 2026-07-04) | key | deep-history fallback + cross-validation | on Yahoo failure / weekly | free tier: 1,000 req/day, 50/hr |
| **FRED** (added 2026-07-04) | key | real macro factors: VIXCLS, DFII10 (real 10y), T10Y2Y (curve), BAMLH0A0HYM2 (HY spread), T10YIE (infl. expectations) | daily | official; levels carried as additive indices (trend ≈ change in pts); publication lags 1 day |
| CBOE delayed chains | none | options intelligence (greeks/OI/IV) | 15 min per symbol sweep | ~15-min delayed; ≤90d expiries; no vanna/charm/dealer inventory |
| Finnhub (free) | key | quotes, news, earnings calendar | 15-20s quotes | congressional endpoint is premium-gated (tested 403) |
| FairEconomy/ForexFactory | none | economic calendar | 30 min | weekly file granularity |
| **FMP** (pending key) | key | congressional trade disclosures (senate-latest/house-latest) | 6h | free tier 250 req/day; disclosures inherently delayed 45+ days; committee data NOT included |
| **Federal Register API** | none | regulatory actions (SEC/EPA/DOE/FDA/HHS/FTC/DOJ/FCC/DoD/DOT/USDA/Fed/OCC) | 6h | publication ≠ market impact; agency→sector map is curated, not official |
| **Treasury FiscalData** | none | upcoming Treasury auctions | 6h+ | schedule only |
| congress.gov API | key (free, NOT configured) | bills, hearings, votes | — | sign up at api.congress.gov/sign-up → set CONGRESS_GOV_API_KEY |
| Anthropic (optional) | key | AI market summary | 10 min cache | falls back to rule-based |

## Tested and rejected (2026-07-04)
- **Stooq** — now behind a JavaScript proof-of-work wall (server-unusable).
- **Senate/House Stock Watcher S3** — 403, project dead; GitHub mirror is a 2020 snapshot.
- **Capitol Trades bff** — CloudFront-blocked for non-browser clients.
- **Finnhub congressional-trading** — premium-gated on the free key.

## Not available free (displayed as unavailable, never estimated)
Real-time congressional trades (structurally impossible — filings are delayed by
law); committee memberships via API; dealer options inventory; ETF fund flows;
block trades; constituent-level breadth (feasible but heavy — parked);
FDA PDUFA calendar; MOVE index.
