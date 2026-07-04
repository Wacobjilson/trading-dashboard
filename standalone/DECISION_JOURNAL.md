# Decision Journal — measuring the human

## Purpose
The least-measured model on the platform is the trader. The decision journal
records pre-trade reasoning BEFORE the outcome exists, attaches the outcome
automatically, and (past the gate) reports whether stated confidence means
anything.

## Inputs (Portfolio tab form, POST /api/journal/decision)
Seven questions: why this trade / evidence for / evidence against / what
invalidates it / assumptions / confidence 1–99% / what would change my mind.
The current regime is stamped automatically at entry.

## Outcome attachment
When a position on the same symbol closes (`position_close`), the newest open
decision on that symbol receives: exit, P&L, R-multiple, won/lost, days held.
Reasoning text is never edited after recording — the point is the comparison.

## Outputs (GET /api/journal/decisions)
Decisions (newest first) + statistics gated at **n≥10 scored decisions**:
realized win rate vs average stated confidence (over/under-confidence read),
win rate by regime. Below the gate: counts only, no early reads.

## AI review (`decisions` mode)
Compares reasoning to outcomes, cites specific decisions, identifies
recurring strengths/mistakes/bias patterns; below the gate it may only
critique reasoning *process* quality.

## Validation
Same rules as every model: no backfill, no editing, sample-size gates,
regime-tagged for later conditioning.

## Known limitations
Symbol-matched attachment assumes one open thesis per symbol; confidence is
a single number (no distribution); n will be small for months — the stats
say so rather than extrapolating.

## Future roadmap
Brier score once n permits; bias taxonomy (chased-entry, early-exit) as
recurring patterns emerge from the AI reviews; link decisions into the
knowledge graph.
