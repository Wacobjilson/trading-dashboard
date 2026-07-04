# Model Registry

Workflow stages: **idea → testing → validation → production → monitoring → retirement.**
Nothing carries production weight without surviving train/test out-of-sample.
This file mirrors `/api/registry` (the live Control Center is authoritative).

## Production

| Model | Evidence | Live monitoring |
|---|---|---|
| RSI(2) mean-reversion (Signals tab) | Walk-forward OOS: 74.7% win, PF 2.05, n=87 (research.py, 2yr Polygon) | Daily signals; regime expectancy accrues via journal tags |
| RS rotation top-3 by 1m RS (Rotation model) | Train PF 2.88 → test PF 2.92, 67% win, n=30 — small sample, labeled candidate | Weekly cross-sectional IC + rolling 13w IC + degrading flag (Research tab) |
| Composite `rs` category (weight 0.70) | IC +0.031 train / +0.017 test — only ablation survivor of 5 bar categories | Continuous rolling IC; IC-by-regime awaits n≥30 buckets |

## Validation (provisional weight, flagged in UI)

| Model | Status |
|---|---|
| Composite `options` category (0.15) | Unvalidated — IC test requires ~60 snapshot days; PCR z calibrates at ≥20 days |
| Composite `macro` category (0.15) | Unvalidated — corr×trend construction; factor-stability flags act as early warning |

## Retired (kept visible with reasons)

| Model | Reason |
|---|---|
| `trend` category | Train IC −0.03; ρ=0.81 redundant with rs (2026-07-03 run) |
| `momentum` category | Train IC −0.06 |
| `volume` category | Train IC −0.16 |
| `volatility` category | Wrong-signed as selection (IC21 −0.213, t=−4.8). Inverted version **pre-registered** for future data only |
| Breadth as per-sector category | Market-level context ± quadrant (duplicates rs) → moved to regime block |
| Intraday futures signals | No combo positive in both train & test net of costs (research_futures.py) |
| Rotation 3m/6m lookbacks, top-1 | Decayed out-of-sample (PF 1.47 / 1.06 / 1.31) |

## Rules

1. Pre-registered acceptance gate: positive in **both** train and test windows.
2. No post-hoc sign flips — a failed signal's inversion goes to the backlog, tested on new data only.
3. Multiple-comparison honesty: the Edge Lab reports how many combos were tested and calls survivors watchlist candidates.
4. Every retired model stays displayed (zero weight) with its measured IC so redemption is observable.
