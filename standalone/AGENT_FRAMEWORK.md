# Agent Framework — MIOS analysts

## Purpose
A modular multi-agent research organization on local infrastructure. Agents
are **configuration entries** (`AGENTS` dict in quanta.py): name, version,
allowed data sources (`parts` — the whitelist of grounding payloads), RAG
query, and role charge. Adding an analyst (Crypto, Energy, Fixed Income,
Supply Chain…) = adding a dict entry; the orchestrator, health tracking,
archive, learning scorecard and UI pick it up automatically.

## The roster (v1)
Macro · Government Policy · Market Structure · Options · Sector · News
Intelligence · Risk Manager · Data Quality · Research Scientist — plus the
**AI Critic** (invoked on disagreements) and the **Research Director**
(synthesis). **Company Intelligence ships dormant** (v0.1): its required
sources (filings, insiders, revisions, contracts) are not integrated, so it
declines to run rather than guess — activation is a config change once
sources exist.

## Structured output contract (no free-form opinions)
Every agent must return JSON (Ollama `format:json`) with exactly:
`observation, supportingEvidence[] (each citing its DATA/DOCS section),
conflictingEvidence[], stance (risk-on|risk-off|neutral|n/a), sectors[],
confidence (0-100), unknowns[], suggestedFollowup` — the framework stamps
`agent, name, version, ts, latencyMs, dataSources, parsed`. Unparseable
output is wrapped with confidence 10 and flagged `unparsed` in the UI.

## Confidence methodology
Self-assessed, evidence-based, instructed to be ≤20 when the domain's data is
unavailable. Self-assessed confidence is a known weak point — which is why
the **learning scorecard** grades stances against realized SPY 10-day forward
returns (gate n≥20 per agent) and displays hit rates next to health.

## Memory
Findings persist in `agent_findings.json` (last 60 cycles) and are what the
learning scorecard, ops panel and morning-brief grounding read.

## Hard limits
Agents read whitelisted platform payloads and return text. No agent output
feeds models, scores, allocation or experiments. Evidence changes models;
AI organizes evidence; humans decide.
