# Research Log

Chronological record of research decisions. Every entry states the question,
method, result, and the production consequence. Harnesses: `research.py`
(strategy battery), `backtest.py` (entry-logic walk-forward),
`research_futures.py` (intraday), `research_categories.py` (category ICs),
plus the live in-app engines (`/api/research`, `/api/edgelab`, `/api/factors`).

## 2026-07-01 — Daily strategy battery (research.py)
- Q: any robust long-only daily edge on the 11 sector ETFs?
- Method: 8 documented systems, train 60% / test 40%, per-trade %.
- Result: RSI(2) family survived OOS (~73–75% win, PF ~2); momentum/breakout did not.
- Production: Signals tab ships RSI(2)<10 + 200-SMA regime, exit >5-SMA.

## 2026-07-01 — Intraday 15m (research_futures.py)
- Result: nothing positive in both windows net of 0.02% cost → Futures tab is context-only. **Negative result kept.**

## 2026-07-02 — Rotation portfolios (research.py)
- Result: top-3 by 1-MONTH RS, monthly rebalance survived (train PF 2.88 → test 2.92, n=30); 3m/6m decayed.
- Production: Rotation model shown as **candidate** with stats attached; alert on composition change.

## 2026-07-03 — Category validation (research_categories.py)
- Q: do the Intel composite's categories predict forward 10d sector-relative returns?
- Method: 54 weekly cross-sections, Spearman IC, train/test, redundancy, ablation, bootstrap CI.
- Result: only `rs` survived; `trend` redundant (ρ0.81); `volatility` wrong-signed (IC21 −0.213, t −4.8).
- Production: weights → rs 0.70 / options 0.15 / macro 0.15; failed categories demoted to zero-weight context.
- Parked hypothesis (pre-registered): inverted-volatility (high-beta) category — test on new data only.

## 2026-07-03 — PCR calibration defect
- Found: absolute PCR anchor mis-read hedged products (SPY ~2.5+ structural).
- Fix: z-score vs own snapshot history; sector-median relative while calibrating.

## 2026-07-03 — Adaptive weighting test (live, /api/research)
- Method: weekly IC split by regime.
- Verdict: **static weights stay** until a regime bucket reaches n≥30 weekly ICs; test runs continuously and the verdict auto-flips when data suffices.

## 2026-07-03 — Phase-4 engines
- Factor attribution (univariate, residual shown), stability flags (|Δρ|≥0.4),
  factor persistence probabilities, Edge Discovery Lab (gate: n_train≥12,
  n_test≥8, mean>0 both, t≥1.5, beats baseline; multiple-comparison caveat in
  every payload), Control Center with stage registry and model-disagreement.

## Standing rules
- No lookahead anywhere; acceptance = positive in BOTH train and test.
- Small n is labeled, never hidden. 2yr Polygon history = one regime cycle.
- Options/macro validation blocked on snapshot history (~60 days), accumulating automatically.
