# Strategy Library

Modular screens (`STRATEGIES` in quanta.py) — adding one is a config entry
with entry/exit definitions and an honest validation stage. **No strategy
reaches Production except through the existing pipeline** (pre-registration →
train/test gate → replication).

| Strategy | Entry | Exit | Stage |
|---|---|---|---|
| RSI(2) mean reversion | RSI(2)<10 above long MA | close > 5d MA | **Production on sector ETFs** (EXP-12 replication); exploratory on single stocks — not validated there |
| Momentum pullback | +25%/60d leader, shallow 5d pullback | 20d MA loss | Exploratory — cross-sectional momentum FAILED on sectors (EXP-04/11); single-stock untested |
| 50% retracement | 50% pocket of 40d swing, uptrend | 61.8% violation | Heuristic — codifies the owner's discretionary setup; no backtest claim |
| Volatility compression | 5d range <55% of 20d avg near highs | direction of expansion | Exploratory — breakout family REJECTED (EXP-01) |
| Volume expansion | 3x volume thrust to 20d high | expansion-bar low | Exploratory — volume category failed IC (EXP-04) |

## Stage vocabulary
production → validation → exploratory → heuristic → rejected. Rejected
families stay listed (institutional memory) but their variants carry the
warning in `conflicting` on every surfaced item.

## Learning verdicts (from tracked outcomes, gate 30)
- **interesting but unproven** → the strategy graduates to a pre-registered
  experiment proposal (Research Director backlog), not to production.
- **false-positive-prone** → tighten or retire the screen.
- The tracker grades surfacing quality only — MFE/MAE from the surfacing
  date, no execution assumptions.

## Deliberately absent screens
Earnings proximity/post-earnings drift (no reliable free earnings-date feed
at market scale), insider/analyst/institutional flows (no free source),
per-symbol news sentiment at scan scale (rate limits). Absent, not
approximated.
