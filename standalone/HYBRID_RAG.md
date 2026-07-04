# Hybrid RAG — modular local retrieval

## Purpose
Better grounding for the AI analyst than TF-IDF alone, with zero cloud
dependencies and graceful degradation.

## Architecture
```
query ─► rankers (independent):  BM25 ─┐
                                 TF-IDF ├─► Reciprocal Rank Fusion (1/(60+rank)) ─► top-k ─► [rerank hook]
                                 vector ┘   (only rankers that returned results)
```
- **BM25** (k1=1.5, b=0.75) — primary lexical ranker.
- **TF-IDF** — the original ranker, kept for backward compatibility and as an
  RRF voter.
- **Vector** — cosine over Ollama embeddings (`OLLAMA_EMBED_MODEL`, default
  `nomic-embed-text`). Activates only if the model is pulled
  (`ollama pull nomic-embed-text`); probed once, embeddings cached in
  `DATA_DIR/rag_embed.json` keyed by chunk hash. Absent → hybrid runs
  lexical-only, silently and correctly.
- **Cross-encoder rerank**: `_rag_rerank` hook only — architecture reserved,
  not implemented (no local cross-encoder worth its latency yet).

## Configuration
`RAG_MODE=hybrid|bm25|tfidf` (default hybrid). All retrieval stays local.

## Validation
Backward compatible: `rag_search()` signature unchanged; `RAG_MODE=tfidf`
reproduces the previous behavior exactly. Retrieval quality comparison is a
listed backlog item (needs a small gold-question set before "better" can be
claimed — the platform does not assert unmeasured improvements).

## Known limitations
RRF constants untuned; chunking (36 lines/4 overlap) can split tables;
embedding cache grows with corpus (pruned only by chunk-hash miss).

## Future roadmap
Gold-question eval set; embedding-based dedup of near-identical chunks;
graph-aware boosting (KNOWLEDGE_GRAPH.md).
