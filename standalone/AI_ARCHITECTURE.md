# AI Architecture — the research analyst layer

```
index.html (AI drawer / ✨ buttons)
      │  POST /api/ai/ask (streamed text) · GET /api/ai/status · POST /api/ai/config
      ▼
quanta.py  ── ai_run() ──► grounding snapshots (AI_PARTS, cache-only)
      │                    RAG retrieval (local *.md + gov event archive)
      ▼
AI_PROVIDERS dispatch ──► _ollama_chat (default)  /  _anthropic_chat
      ▼
Ollama REST (host) ──► qwen3:14b (or any pulled model)
```

## Principles
- **The frontend never calls Ollama.** All AI traffic goes through the backend,
  which assembles grounded prompts and enforces the safety preamble.
- **Provider-modular:** `AI_PROVIDERS` is a dict of adapters with one
  signature (`messages, opts, stream_cb`). Switching Ollama→Anthropic (or a
  future OpenAI adapter) is `AI_PROVIDER=` config, zero application changes.
  New Ollama models are a dropdown switch at runtime (`POST /api/ai/config`),
  no restart.
- **Graceful degradation:** if Ollama is down, `/api/ai/status` reports it,
  the drawer shows it, streamed requests end with a plain-text error line —
  and nothing else in the platform is affected (no view imports the AI layer).
- **Read-only by construction:** `ai_run()` only reads cached view payloads
  and returns text. There is no code path from AI output into trades, weights,
  allocation, experiments, registry or state files. See AI_LIMITATIONS.md.

## Configuration (env, all optional)
`AI_ENABLED` `AI_PROVIDER` `OLLAMA_HOST` `OLLAMA_MODEL` `AI_TEMPERATURE`
`AI_NUM_CTX` `AI_MAX_TOKENS` `AI_TIMEOUT` `AI_RETRIES`
(+ `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` for the anthropic adapter).
Runtime overrides via `POST /api/ai/config` (model, temperature, maxTokens,
numCtx, timeoutS, retries, enabled, provider, host) — runtime only; persist
by writing the same values into `.env`.

## Performance
- Prompt cache: sha1(mode+messages) → 10-min TTL (skipped when conversation
  history is present).
- Streaming end-to-end (Ollama NDJSON → chunked plain text → fetch reader).
- Cancellation: client abort closes the socket; the backend's write fails,
  which closes the Ollama connection and stops generation.
- Telemetry: last 60 calls (mode, model, latency ms, prompt/output tokens)
  in `/api/ai/status`.

## Future compatibility (designed, not implemented)
The adapter signature and `AI_PARTS`/`AI_MODES` registries are the extension
points: vision models (add an images field to the adapter contract), PDF/paper
ingestion (new RAG source in `_rag_build`), multiple local models / routing
(per-mode `model` override in `AI_MODES`), voice (frontend concern only).
