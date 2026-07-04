# Decision Log

Machine-readable decision records live in the data directory (Docker volume
`./data`), human-readable rationale belongs here.

## Stored automatically

- `quanta_state.json` — every position with entry-time tags: market regime,
  RS rank group, breadth, vol percentile, plus stop/target (the plan). Closed
  trades keep the tags, exit and realized P&L.
- `predictions_history.json` — daily published scores + P(beat SPY 10d) per
  sector (feeds calibration + weekly review).
- `scores_history.json` — daily composite scores (movers, real sparklines).
- `options_history.json` — daily IV30/OI/PCR/GEX/DEX per symbol.

## Review cadence

- **Weekly** (automated, Research tab): matured top-3 hit rates + reliability
  table. Failures classify crudely as regime-change / factor-break-flagged /
  within-noise, given available evidence.
- **Quarterly** (manual): re-run `research_categories.py` and the Edge Lab on
  accumulated data; promote/demote per MODEL_REGISTRY.md rules; append the
  decision + numbers to RESEARCH.md.

## Entries

### 2026-07-03 — Allocation framework v1 shipped
Conviction/vol weighting over gated candidates; regime-scaled invested budget
(heuristic, documented in PORTFOLIO_ENGINE.md); 25% cap. Rationale: only
validated inputs (RS composite, base-rate probabilities) drive ranking; sizing
uses vol, the one input that needs no validation. Adaptive allocation learning
is DATA-GATED: it requires the prediction log and journal tags now being
collected — no allocation logic will change without a measured improvement.
