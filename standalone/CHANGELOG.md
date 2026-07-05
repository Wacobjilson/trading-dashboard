# Changelog (standalone platform)

## 2026-07-05 · Phase 16 — MIOS (Market Intelligence Operating System)
- **Agent framework**: 10 analyst agents as config entries (AGENTS dict) with
  whitelisted data sources, versions, and a structured JSON output contract
  (observation / supporting+conflicting evidence with section citations /
  stance / sectors / confidence / unknowns / follow-up). Company Intelligence
  ships dormant (sources not integrated — declines to run rather than guess).
- **Orchestrator**: event inbox → sequential agent runs → disagreement
  detection → AI Critic challenge → Research Director synthesis (WHAT
  CHANGED / MATTERS MOST / SECTORS / WEAK CLAIMS / RESEARCH TODAY / IGNORE)
  → archived (60 cycles). Scheduled daily (MIOS_CYCLE_HOURS) + on-demand;
  honest constraint stated: ~10-15 min/cycle on a local 14B, so LLM cycles
  are scheduled while deterministic loops monitor continuously.
- **Continuous learning**: agent stances graded against realized SPY 10d
  forward returns (gate n≥20/agent) — grades AI interpretations, never
  trading models.
- **Operations** (/api/ops + MIOS panel): per-host fetch latency/errors,
  cache hit rate, RAG stats + embedding status, AI token usage by mode,
  feed freshness, loop-error counters, agent health. Morning AI mode now
  grounds in the latest cycle. Docs: AGENT_FRAMEWORK, AGENT_ORCHESTRATOR,
  WORLD_MODEL, EVENT_PIPELINE, MARKET_INTELLIGENCE, OPERATIONS,
  SOURCE_REGISTRY.

## 2026-07-05 · Phase 15 fixes — production hardening
- **Fix #1**: `research_log_loop` — score snapshots + allocation prediction
  log now write on a schedule (4x/day, date-deduped), not only when a tab is
  opened. Calibration can finally mature.
- **Fix #2**: FOMC_DECISIONS verified against federalreserve.gov — all 44
  dates 2021–2026 match official statement press-release links exactly;
  2019–2020 match the historical pages (canceled Mar-2020 meeting correctly
  excluded). Verification recorded in the code comment.
- **Fix #3**: `smoketest.py` — 30 views + invariants run on synthetic data as
  a Docker build gate (~2s, no network needed). First automated regression
  net for the platform.
- Also: keyboard shortcuts no longer fire from textareas (decision-journal
  bug); synthetic bars use a stable seed (PYTHONHASHSEED made demo bars
  differ across restarts).
- **Tab consolidation 13 → 10**: News + Calendar merged into Markets;
  Entries scanner merged into Chart. Futures kept as an execution monitor
  (its no-signal-edge verdict stands, EXP-02).

## 2026-07-04 · Phase 14 — Research Director (the platform improving itself)
- **/api/director**: platform health (self-explaining metrics), evidence-
  growth counters (each states what it unlocks), meta-learning parsed from
  EXPERIMENT_LOG.md (outcome mix, pre-registration rate, velocity), priority
  engine (10-item backlog scored on infoGain/tradingValue/cost/overfitRisk/
  novelty with live unblock % from data counters; stated ranking formula),
  knowledge graph (docs↔experiments↔beliefs↔models via citation scan),
  code inventory for the AI auditor. Research tab gains the Director section.
- **Decision journal**: 7-question pre-trade record (regime-stamped, never
  edited), outcome auto-attached at position close (P&L, R, days held),
  stats gated n≥10 (confidence vs realized win rate, by regime). Portfolio
  tab card + `decisions` AI review mode.
- **Hybrid RAG**: modular rankers (BM25 + TF-IDF + optional Ollama-embedding
  vector) fused with RRF; RAG_MODE config, TF-IDF backward-compatible;
  embeddings cached on disk; cross-encoder hook reserved. Degrades to
  lexical-only without an embedding model.
- New AI modes: director (daily report), monthly (review), audit (code
  auditor — inventory-grounded, never modifies), decisions. Governance
  unchanged: evidence changes models, AI organizes evidence, humans approve.
- Docs: RESEARCH_DIRECTOR, KNOWLEDGE_GRAPH, HYBRID_RAG, RESEARCH_PROCESS,
  AI_AUDITOR, DECISION_JOURNAL.

## 2026-07-04 · Phase 13 — local AI research analyst (Ollama)
- Provider-modular AI layer (ollama default, anthropic adapter; config-only
  switching, runtime model swap via /api/ai/config). Frontend never calls
  Ollama — backend grounds every prompt in live platform payloads + TF-IDF
  RAG over the local docs, with a safety preamble on every request.
- Drawer UI (✨ AI): 12 modes (ask/morning/market/sector/company/portfolio/
  government/critique/journal/models/experiment/explain) + 8-voice investment
  committee + 5 structured debates, streamed with cancel, conversation
  history, telemetry (latency/tokens), prompt cache; ✨ explain buttons on
  gov brief / exposure profiles / chart setups.
- Hard boundary: AI output has no code path into trades, weights, allocation
  or research state — explain/critique only. Degrades gracefully when Ollama
  is off. New docs: AI_ARCHITECTURE, OLLAMA_INTEGRATION, PROMPT_LIBRARY,
  RAG_ARCHITECTURE, AI_LIMITATIONS.

## 2026-07-04 · Phase 11 — policy research workstation
- **Morning brief** at the top of the Government tab (overnight items,
  changes vs snapshot history, sectors to watch, approaching catalysts,
  portfolio note, assumptions in play) — rule-assembled, no AI narrative.
- **Event briefings**: institutional research notes (why it matters, risks,
  exposed positions/watchlist, market context, precedent, multi-dimension
  scorecard with explanations, limitations) for FOMC, final rules,
  advanced-stage bills, conviction clusters.
- **Measured event study**: scheduled FOMC decision days 2019–2026 vs
  baseline (SPY + XLF/XLU/XLK) — measured n=59: |move| 0.92% vs 0.78%
  baseline (~1.2x, modestly elevated), 51% up → no directional edge.
  Other event types: event archive accumulates (GOV-04, gate ≥30/kind)
  instead of fabricated similarity scores.
- Bill lifecycle stages + next milestones; exposure expanded to 17 policy
  dimensions (click-through profile); catalysts gain urgency/status/research
  columns. All still descriptive — nothing feeds scores/allocation.

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
