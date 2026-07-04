# Research Director — the platform improving itself

**Mission:** "Based on everything the platform has learned, what is the single
highest-value improvement to make next?" The Director advises; humans approve.
Nothing here modifies validated logic, weights, allocation or experiments.

## Purpose
Turn the platform from a collection of tools into a research organization:
continuous self-assessment (health, evidence growth, meta-learning), a ranked
improvement backlog, and AI-written daily/monthly reports grounded in the
deterministic meta-views.

## Inputs
Scorecards, registry, integrity (beliefs), calibration, drift, assumptions
(all cached views); EXPERIMENT_LOG.md and RESEARCH_DEBT.md (parsed);
data-store counters (options snapshots, predictions, closed trades, decisions,
disclosures, heat snapshots, event archive, deep cache).

## Outputs (`/api/director`, Research tab top section)
- **topRecommendation** — the #1 backlog item by priority score.
- **health** — 8 metrics, each with its `why`.
- **evidenceGrowth** — every counter states what data maturity unlocks.
- **metaLearning** — experiments/outcomes/pre-registration rate/velocity
  parsed from the log (keyword-classified, log is source of truth).
- **backlog** — priority engine (below).
- **graph** — knowledge-graph links (KNOWLEDGE_GRAPH.md).
- **codeStats** — measured inventory for the AI auditor (AI_AUDITOR.md).

## Priority engine
Each item carries: infoGain, tradingValue, cost, validationDifficulty,
overfitRisk, novelty (0–100 curated heuristics with a written `why`),
requiredData + gate + measured **unblockPct** from live counters, timeline,
dependencies, confidence. Ranking = 0.45·infoGain + 0.2·tradingValue +
0.2·unblock − 0.15·cost − 0.15·overfitRisk — a stated display heuristic,
optimizing learning per unit effort, not feature count.

## Reports (AI modes, grounded in the director payload)
`director` = daily research report (FACTS / INTERPRETATION / UNKNOWNS /
RECOMMENDED RESEARCH); `monthly` = comprehensive review (maturity, knowledge
gained/lost, retire/protect, greatest uncertainty). Weekly committee minutes
remain the deterministic `/api/committee`.

## Validation
Deterministic parts are counts and parses — auditable against their sources.
AI reports are interpretation, marked as such, never parsed back.

## Known limitations
Backlog dimensions are curated judgments; meta-learning n is tiny (~14
experiments); doc parsing is keyword-based; "documentation coverage" counts
files, not quality.

## Future roadmap
Auto-run data-gated experiments when counters hit gates (with pre-registered
specs); backlog item lifecycle (proposed→approved→done) with human sign-off
recorded in DECISION_LOG.md; velocity trend alarms.
