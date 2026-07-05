# Event Pipeline

Every event class already flows through the required stages — implemented in
the loop that owns it, not a monolithic queue (single-process design):

| Stage | Where it happens |
|---|---|
| Collection | quotes/bars/live/options/news/calendar/congress/deep loops |
| Validation | per-source parsers; failed quotes go stale, never fabricated |
| Deduplication | alert keys, congressional filing ids, event-archive keys |
| Classification | news CATEGORY_RULES, policy-area classifier, bill stages |
| Entity extraction | ticker/member/agency fields; sector maps |
| Sector mapping | CONGRESS_SECTOR_MAP, AGENCY_SECTOR, POLICY_SECTOR |
| Portfolio mapping | exposure hits in briefings/risk agent |
| Historical similarity | FOMC event study; other kinds accumulate (GOV-04) |
| Knowledge-graph update | event archive + heat snapshots (append-only) |
| Agent assignment | orchestrator inbox → domain agents |
| Evidence synthesis | Critic + Research Director synthesis |
| Research lookup | RAG retrieval inside every agent prompt |
| Confidence scoring | structured findings + learning scorecard |
| Alert generation | alert engine (~30s sweeps, deduped) |
| Archival | agent_findings.json, congress_trades.json, histories |

## Guarantees
Point-in-time snapshots for anything that arrives late (disclosures); error
payloads never cached; per-host fetch errors counted in ops (silent failure
is a tracked number, not a hope).

## Non-goals
No message broker, no worker pools — measured load (single user, 3–5ms warm
endpoints) doesn't justify them; STRESS_TEST.md documents the scale limits.
