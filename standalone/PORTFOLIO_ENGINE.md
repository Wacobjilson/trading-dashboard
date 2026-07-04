# Portfolio Construction Engine

`/api/allocation` converts research outputs into a **suggested allocation
framework** (explicitly not advice — the payload says so). Every step is a
shown formula; nothing is a black box.

## Pipeline

1. **Candidates** = the opportunity ranking (composite score + probability +
   regime fit + conflicts).
2. **Inclusion gate** (each failure is listed under "excluded" with reasons):
   composite ≥ 55, historical P(beat SPY 10d) > 50%, risk score < 70.
3. **Conviction** = (score − 50)/50 × confidence.
4. **Raw weight** ∝ conviction ÷ annualized vol (63d) — risk-adjusted conviction.
5. **Invested budget** by regime (heuristic table, displayed):
   Trending Bull 90% · Bull Pullback 75% · Bear Rally 50% · Trending Bear 30%,
   −15pts in a high-vol regime. Remainder = cash.
6. **Cap** 25% per sector, renormalized.
7. **Explainability**: per line — whyThisSector (evidence), whyThisSize
   (the formula with this sector's numbers), against (conflicts), wouldChange
   (concrete triggers). Plus book-level factor exposures (Σ w×β) with ⚠ at
   |exposure| ≥ 0.35.

## Expected-return honesty

"Expected" 10d numbers are the **median and quartiles of historical base
rates** for the sector's current RS rank group — descriptions of a 2-year
sample, not forecasts. Confidence intervals and n live in the probability
engine payload.

## What updates it

Scores (120s cache), probabilities/regime (600s), factor betas (600s).
Allocation cache 300s. Prediction logging happens here: every day's published
scores + P(beat 10d) are appended to `predictions_history.json` for the
calibration engine.

## Known limitations

- Regime-invested-budget table is a stated heuristic, not fitted (would need
  multiple regime cycles to fit honestly).
- Vol is trailing 63d; shocks lag.
- Factor exposures use overlapping univariate betas — approximate by design.
