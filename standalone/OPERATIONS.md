# Operations & Observability

`GET /api/ops` + the Research tab MIOS panel. Nothing operates as a black box
— every number below is a live counter, not an estimate.

| Signal | Source |
|---|---|
| Agent health | runs, parse failures, avg latency, last confidence (last 10 cycles) |
| Cycle state | running flag, archived cycle count, last error |
| Source latency | per-host last-call ms + error/call counts (every `http_get_json`) |
| AI latency & tokens | last-60-call telemetry: per-mode counts, avg s, prompt/output tokens |
| Cache | hit rate, entry count (every `cache_get`) |
| RAG | chunk count, active mode, search count, embedding status (active/inactive with the exact `ollama pull` needed) |
| Data freshness | bar ages, live-quote age, congressional fetch age |
| Error rates | loop-error counters by site (`_ops_err`) — silent failure is now a visible number |
| Learning | per-agent stance hit rate vs realized SPY 10d (gate n≥20) |

## Known blind spots (stated)
Counters reset on restart (process-lifetime, not persisted); AI telemetry
window is 60 calls; per-endpoint response-time histograms not collected
(cold/warm spot-measurements live in STRESS_TEST.md); queue depth is always
0/1 by design (no worker pool — single-process, measured 3–5ms warm).

## Runbook
- Cycle stuck? `/api/agents` → running + lastError; Ollama down shows in
  `/api/ai/status`; cycles skip and retry half-hourly.
- Feed stale? ops → dataQuality feeds + elevatedErrorHosts names the host.
- Loop errors climbing? the counter names the site (`agent:macro`,
  `agents_save`…) — grep it.
