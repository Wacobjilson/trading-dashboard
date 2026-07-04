# RAG Architecture — local knowledge base

Zero-dependency retrieval (stdlib only, like everything else here): no
embeddings server, no vector DB. TF-IDF over chunked local documents.

## Corpus (`_rag_build`, rebuilt every 30 min on demand)
- Every `*.md` in the app directory — RESEARCH.md, EXPERIMENT_LOG.md,
  MODEL_REGISTRY.md, FACTOR_LIBRARY.md, DECISION_LOG.md, ROADMAP.md,
  RESEARCH_DEBT.md, CHANGELOG.md, PORTFOLIO_ENGINE.md, ALLOCATION_METHODS.md,
  CONFIDENCE_CALIBRATION.md, GOVERNMENT_INTELLIGENCE.md, CONGRESSIONAL_DATA.md,
  DISCLOSURE_LIMITATIONS.md, DATA_SOURCES.md, the AI docs themselves…
  (the Dockerfile ships them into the image).
- The government **event archive** (congress_trades.json → events) serialized
  as dated one-liners — institutional memory of rules/bill actions.
- Chunking: 36 lines with 4-line overlap, per-chunk term frequencies.

## Retrieval (`rag_search`)
Query = user question + mode's default query + symbol/topic. Score =
Σ tf(t)/len × log(1 + N/(1+df(t))) over query tokens (≥3 chars). Top-k
(default 3) chunks are injected as `### DOCS: <filename> (relevance …)`
sections, capped 1,500 chars each.

## Why prompts always carry both DATA and DOCS
DATA sections are live payloads (what is true now); DOCS are the platform's
written research memory (what was tested and decided). The safety preamble
requires citing sections, so answers are auditable against both.

## Extension points (designed, not implemented)
New sources = append to `_rag_build` (e.g. ingested PDFs/papers as text,
weekly committee minutes exports). Retrieval quality upgrades (embeddings
via Ollama `/api/embeddings`) would swap `rag_search` only.

## Honest limitations
Keyword TF-IDF misses synonyms; chunks can split tables; the corpus is only
as current as the docs — which is why the docs are updated as part of every
research decision (platform rule since Phase 4).
