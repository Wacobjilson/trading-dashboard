# Research Radar

An agent that **continuously hunts for newly-published studies, reports and
data** on the capital-cycle / AI-bubble themes, AI-summarizes what it finds,
and feeds that synthesis into the PM's decision — so the PM reasons with fresh
evidence, not just the hardcoded historical analogs (`CC_REFERENCE`).

## What it does
- **Themes** (`RADAR_THEMES`) — configurable capital-cycle search themes: AI
  capex-vs-returns, AI-bubble warnings, data-center overbuild, enterprise AI
  ROI, insider selling, valuation extremes, AI/data-center credit stress.
- **Collect** (`radar_collect`) — for each theme, pull recent articles from the
  **GDELT news index** (keyless article-list mode, deduped, paced 6s for
  GDELT's 1 req/5s limit). Titles, source domains, dates, URLs.
- **Summarize** (`radar_summarize`) — the local LLM extracts the concrete,
  decision-relevant findings/data points being reported (studies, numbers,
  warnings) and writes a 3–4 sentence PM-facing synthesis of what current
  research says about AI capital-cycle top risk. Grounded strictly in the
  collected headlines; runs through the single-Ollama gate.
- **Feed the PM** (`AI_PARTS["radar"]`) — the synthesis + per-theme headlines
  are injected into the `pm-desk` and `morning` AI briefs, so the PM's read
  incorporates the latest published research automatically.
- **Loop** (`radar_loop`, `RADAR_HOURS` default 8) — refreshes continuously.

## Surfaced in the UI
Capital Cycle tab → "Research radar" card: the AI PM synthesis + the source
articles by theme (linked, with source domain). `/api/radar`.

## Honest limits (labeled everywhere)
- Sourced from **news coverage** (GDELT), then **AI-summarized** — headlines
  are **secondhand and UNVERIFIED**. The radar surfaces *what is being
  reported*; it does NOT confirm a study exists or that its numbers are right.
- The LLM can misread a headline — it's instructed to summarize only what the
  headlines state and never invent numbers, but treat it as a **research feed,
  not a fact-checker**. Verify before relying.
- GDELT indexes public web news, not paywalled academic journals — coverage is
  broad but not authoritative or complete.
- Persisted in `research_radar.json` (data volume, gitignored).

## Relationship to `CC_REFERENCE`
`CC_REFERENCE` = anchored, curated historical top signatures (Dotcom,
Blackstone, SPACs) — timeless, hand-verified. The Radar = the *living* layer
that keeps finding new studies/data. Both feed the PM; the Radar is the
"always looking" half the user asked for.
