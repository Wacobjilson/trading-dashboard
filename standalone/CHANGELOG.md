# Changelog (standalone platform)

## 2026-07-04 · Phase 10 — Government & Policy Intelligence Center
- **Congress tab rebuilt as "Government"** (one tab, sectioned): sector
  government exposure (curated 0–3 ratings + live counts), congressional
  activity, legislative intelligence (congress.gov bills with policy-area
  classification + sector mapping), regulatory feed with policy badges,
  political calendar, filterable catalyst dashboard, company government
  profiles (knowledge-graph lite), and a government research section.
- **EXP-13 pre-registered** (follow-the-filing, gate fixed before results);
  GOV-02/GOV-03 registered data-gated; daily sector-heat snapshots persist
  so they can mature. New endpoint `/api/government`. Everything descriptive —
  nothing government-derived feeds scores or allocation.
- **Chart integrity fix:** failed quote fetches were silently replaced by
  mock random-walk prices (seeded from stale levels) and merged into real
  charts — the "giant red bar". Real-data mode now lets quotes go stale
  instead of fabricating; UI additionally rejects mock/±12% outlier ticks
  before touching the forming candle. Mock quotes remain demo-mode only.
- Finnhub key configured (real quotes, ~60/min budget); corrected
  congress.gov key.
- Doc rename: LEGISLATIVE_INTELLIGENCE.md → GOVERNMENT_INTELLIGENCE.md.

## 2026-07-04 · Phase 7 — research-director cycle
- **Deep history**: research matrices now use Yahoo v8 adjusted daily (~25y per
  symbol; ~8y common window bounded by XLC), quality-checked against the
  Polygon overlap (diff % stored per symbol). Live signal paths unchanged.
- **Partial-correlation control**: factor drivers must survive |ρ_partial(SPY)|
  ≥ 0.15 — beta-in-disguise links demoted, flagged `betaOnly`.
- **Hypothesis generator** (`/api/hypotheses`): auto-proposes ranked research
  from live anomalies with EXPERIMENT_LOG dedupe links.
- New docs: EXPERIMENT_LOG.md, RESEARCH_DEBT.md, CHANGELOG.md.

## 2026-07-04 · Phase 6 — self-evaluation
Scorecards (model replays, rolling windows, health/recommendation), assumption
monitor, drift detection, counterfactual baselines, live research priorities,
auto committee minutes, governance fields, enriched prediction log. Fix:
history writers create the data dir.

## 2026-07-04 · Phase 5 — decision engine
Allocation framework (gated conviction/vol, regime budget), 6 sizing methods,
8-scenario simulator, live confidence calibration (no backfill).

## 2026-07-03 · Phase 4 — factor intelligence
10-factor library (+HYG), univariate attribution with residual, stability
flags (|Δρ|≥0.4), Edge Discovery Lab (gated combo search), research control
center, entry-context tagging.

## 2026-07-03 · Phase 3 — research & prediction
Regime classifier, probability engine (Wilson CIs on effective n), historical
analogs, live IC validation, opportunity ranking, journal groups.

## 2026-07-03 · Phase 2 — evidence-based scoring
Category IC validation (only RS survived; volatility wrong-signed; trend
redundant) → reweight rs 0.70/options 0.15/macro 0.15; PCR z-calibration fix;
regime strip; proper BS gamma-flip; dual-stack listener (2050ms→2ms localhost).

## 2026-07-03 · Phase 1 — intelligence platform
Intel composite, CBOE options intelligence, macro insight, market summary,
portfolio risk analytics, anchored VWAP, keyboard shortcuts.

## 2026-07-02 and earlier
Alerts engine, live charts, portfolio tracking, rotation model (top-3/1m),
RSI(2) signals, entries scanner, Docker deploy. Original k8s/Go/Next.js stack
superseded by the standalone Python platform.
