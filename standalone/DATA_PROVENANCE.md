# Data Provenance

Every number in the app should answer: where from, which provider, which
endpoint, cached?, how old, what transform, reproducible?

## Provenance by value class
| Value | Provider / endpoint | Transform | Cache | Source label |
|---|---|---|---|---|
| Daily bars, charts | Polygon `v2/aggs/.../day` | adjusted OHLCV | 6h | `source` field (polygon\|synth) |
| Live quotes | Finnhub `/quote` | none | ~30s | `_live[sym].source` |
| Deep history | Yahoo v8 (Tiingo fallback) | adjusted close | 7d | `provider` in deep cache |
| Sector composite | derived from bars | RS/options/macro categories, weighted | 120s | `alphaStatus` = DESCRIPTIVE |
| RSI(2) signals | bars | Wilder RSI, SMA gates | 120s | verified via `_rsi_ser` cross-check |
| Options GEX/IV | CBOE delayed chains | BS greeks, naive dealer convention | 15m | stated assumption on every payload |
| FRED factors | FRED series | level→100+Δ additive index | daily | series ids in FACTOR_LIBRARY.md |
| Congressional | FMP senate/house-latest | field-mapped, delay computed | 6h | source + collectedAt per row |
| Government events | Fed Register / congress.gov | policy-area keyword class | 6h | `source` per item |
| Deep-value fundamentals | FMP stable (profile/km-ttm/ratios-ttm) | percentile pools, reverse-DCF | 6d | `source` field per record |
| SEC filings | EDGAR submissions API | form/date extraction | on demand | accession + CIK, official |
| ODE market store | Polygon grouped-daily | liquidity gate | 1/day | `market_bars.json.gz` |

## Independent reproducibility
- Prices: cross-checked Polygon vs Yahoo vs Finnhub — 0.00% divergence on SPY
  (SYSTEM_AUDIT.md). Yahoo adjusted-close verified within 0.52% of Polygon.
- RSI(2): two implementations agree (verify check #4).
- Reverse-DCF: bisection on a transparent PV model; inputs (FCF yield, EV,
  market cap) all from FMP and shown.

## Where provenance is weakest (documented, not hidden)
- GEX dealer positioning: an *assumption* (naive +call/−put), not measured —
  the root of the options tree is unverifiable in free data.
- FMP TTM ratios: computed by FMP, not independently reproduced from raw
  statements (SEC XBRL reproduction is a listed future check).
- FOMC dates: verified once against the Fed calendar (2026-07-05); re-verify
  on append.
