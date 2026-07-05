# Living World Model

The world model is the union of the platform's persistent, evolving stores —
not a separate database:

| Layer | Store | Evolves via |
|---|---|---|
| Prices/regimes | bars + deep cache + weekly states | market data loops |
| Entities & links | knowledge graph (docs↔experiments↔beliefs↔models) | citation scans, registry updates |
| Government | event archive + heat snapshots + trades store | congress loop (point-in-time) |
| Research | EXPERIMENT_LOG, registry, belief register, assumptions | governance process only |
| Human judgment | decision journal, trade journal | user entries + auto outcomes |
| AI interpretation | agent findings archive (60 cycles) | intelligence cycles + learning scorecard |
| Narratives | agent observations/stances over time | graded against realized returns |

Relationships strengthen/weaken as evidence accumulates: beliefs carry dated
confidence evolution; agent stances accumulate hit rates; data-gated
experiments carry live unblock counters. Nothing in the world model is
edited retroactively — snapshots and logs are append-only by design, because
reconstruction-from-current-state is how lookahead bias gets in.

## Querying it
Structured: /api/director (graph), /api/agents (findings), /api/government,
/api/integrity. Natural language: the AI drawer — hybrid RAG retrieves the
relevant docs/archives before any answer.

## Limitations
The graph is citation-scanned (prose links without IDs are missed); narrative
tracking is stance-level, not full narrative graphs; company-level nodes wait
on company data sources (dormant agent).
