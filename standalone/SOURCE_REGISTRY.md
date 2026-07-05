# Source Registry

The canonical data-source registry (auth, refresh, limitations, rejected
sources) lives in **DATA_SOURCES.md** — one registry, not two.

This file adds the MIOS view: which agents are allowed which sources.

| Agent | Allowed grounding (AI_PARTS whitelist) |
|---|---|
| Macro Analyst | macro, factors, regime |
| Government Policy Analyst | government |
| Market Structure Analyst | regime, scores, opportunities, probabilities |
| Options Analyst | options |
| Sector Analyst | scores, opportunities, factors, government |
| News Intelligence Analyst | alerts |
| Risk Manager | portfolio, allocation, regime, options, government |
| Data Quality Analyst | measured data-quality report |
| Research Scientist | director, integrity, assumptions, calibration |
| Company Intelligence | (none — dormant until filings/insider sources exist) |
| AI Critic | the disputing findings only |
| Research Director (synthesis) | all findings + challenges |

Rules: agents cannot read outside their whitelist (the prompt only contains
whitelisted sections); every claim must cite its section; sources with no
integration produce a dormant agent, never guesses. Per-host fetch latency
and error rates for every underlying source are live in `/api/ops`.
