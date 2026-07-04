# Confidence Calibration

**Question:** when the platform publishes "P(beat SPY over 10d) = 60%", does it
come true ~60% of the time?

## Method (live, out-of-sample by construction)

- Every day the allocation engine logs each sector's published score, P(beat
  SPY 10d) and confidence to `predictions_history.json` (started 2026-07-03).
- A prediction **matures** 10 trading days later, when the realized
  SPY-relative return is known.
- Matured predictions are bucketed by published probability (5-pt buckets);
  `/api/calibration` reports predicted vs realized per bucket — a reliability
  table (diagram in the Research tab).
- First read requires **≥30 matured predictions**; "calibrated" = every bucket
  with n≥10 within ±15pts. Recalibration (e.g. shrinking probabilities toward
  50%) happens only on this evidence, never by feel.
- The same log powers the **weekly decision review**: for each matured day,
  did the top-3 scored sectors beat SPY over the next 10 sessions?

## Why not backfill from history?

Backfilled "calibration" would test the model on the data that built it —
trivially flattering. Only predictions published before their outcomes count.
This means calibration starts empty and fills at 11 predictions/day.

## Decision-vs-luck note

Positions are tagged at entry (regime, RS group, breadth, vol percentile).
A good decision is one where the tagged evidence was positive at entry —
independent of outcome. With enough closed trades the journal separates
expectancy by entry conditions (decision quality) from realized P&L (which
includes luck). Small n is always labeled.
