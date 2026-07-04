# Research Process — how this platform learns

## The lifecycle every idea follows
1. **Hypothesis** — auto-generated (`/api/hypotheses`) or human; deduped
   against RESEARCHED_TOPICS institutional memory.
2. **Pre-registration** — EXPERIMENT_LOG.md entry with the exact test spec
   and acceptance gate written BEFORE results exist.
3. **Validation** — train/test both-positive gate; permutation/bootstrap
   where applicable; overlap-adjusted effective n.
4. **Replication** — parameter/cost/regime perturbation grids (CSO layer).
5. **Calibration** — stated probabilities checked against outcomes.
6. **Consequence** — weights/stages change only after the gate, and the
   change is logged (DECISION_LOG.md, CHANGELOG.md).
7. **Retirement** — failures stay on record (negative-results policy).

## Meta-learning (measured by the Director)
Experiments logged, outcome mix, pre-registration rate, velocity by month —
parsed from the log itself. Standing meta-findings: the both-windows-positive
gate caught every curve-fit so far; pre-registration is the only defense
against post-hoc sign flips; rejection is cheaper than confirmation at this
sample size.

## Rules that protect the process
- No post-hoc sign flips, ever (volatility category is the cautionary tale).
- Data-gated tests cannot be peeked at early (gates are in the Director
  backlog with live counters).
- The human approves all changes; AI organizes evidence and drafts critique.
- Docs are updated as part of every research decision — they ARE the
  institutional memory that RAG serves back.

## Known limitations
~14 experiments is a young record; velocity stats are counts, not trends yet.

## Future roadmap
Time-from-hypothesis-to-verdict tracking once log entries carry both dates;
false-positive catch-rate per validation method as n grows.
