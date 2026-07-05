# Agent Orchestrator

## Cycle flow (`run_agent_cycle`)
1. **Event inbox** — recent platform events (alerts, government archive
   entries), already validated/deduplicated/classified upstream.
2. **Agent runs** — every non-dormant agent analyzes its whitelisted data +
   the shared inbox, sequentially (one local model — parallelism would just
   queue inside Ollama).
3. **Disagreement detection** — confident (≥40) risk-on vs risk-off stances
   trigger the **AI Critic**, which attacks both positions and says when the
   evidence is too weak to decide.
4. **Research Director synthesis** — WHAT CHANGED / WHAT MATTERS MOST /
   SECTORS & EXPOSURE / DISAGREEMENTS & WEAK CLAIMS / RESEARCH TODAY /
   IGNORE (findings under confidence 30 are routed to IGNORE by charge).
5. **Archive** — full cycle (inbox, findings, challenges, synthesis, wall
   time) persisted; nothing reaches the user without passing this pipeline.

## Scheduling — the honest version
A 14B local model costs ~100s per call; a full cycle is ~10–15 minutes.
"Agents on every tick" would be theater. So: **deterministic loops monitor
continuously** (quotes/bars/options/congress/deep/research-log — as before);
**LLM cycles run every `MIOS_CYCLE_HOURS` (default 24, before the user's
morning) plus on-demand** (▶ button / `POST /api/agents/run`). Set
`MIOS_CYCLE_HOURS=0` to disable scheduling.

## Failure behavior
A failed agent becomes a zero-confidence "AGENT FAILED" finding (visible,
counted in ops) — the cycle continues. If Ollama is unreachable the
scheduled cycle is skipped and retried half-hourly. The platform never
depends on a cycle existing.

## Outputs
`GET /api/agents` (health, last cycle, learning scorecard),
`GET /api/ops` (observability), morning AI mode grounds in the latest cycle.
