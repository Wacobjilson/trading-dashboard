# Ollama Integration

## Requirements
- Ollama installed on the Windows host, a pulled chat model
  (default `qwen3:14b`; `ollama pull qwen3:14b`).
- Ollama listening on `127.0.0.1:11434` (its default) is sufficient —
  Docker Desktop's `host.docker.internal` proxies container traffic to host
  loopback, and the compose file adds `extra_hosts: host-gateway` for
  non-Desktop engines. If the container still can't reach it, set the
  Windows env var `OLLAMA_HOST=0.0.0.0` for the Ollama service and restart it.

## Endpoints used
- `POST {host}/api/chat` — chat completion, `stream:true` NDJSON lines,
  options `temperature` / `num_ctx` / `num_predict`.
- `GET {host}/api/tags` — installed models (drives the drawer's model
  switcher and the reachability probe in `/api/ai/status`).

## Model switching
The drawer's model dropdown calls `POST /api/ai/config {"model": "..."}` —
takes effect on the next request, no restart. Any model listed by
`/api/tags` works; reasoning models (qwen3) emit `<think>` blocks which the
UI collapses to "… model reasoning …" while streaming and strips from the
saved conversation.

## Failure behavior
| Failure | Behavior |
|---|---|
| Ollama not running | status shows offline + reason; requests return a one-line plain-text error; platform unaffected |
| Timeout (`AI_TIMEOUT`, default 240s) | retried up to `AI_RETRIES` for non-streamed; streamed requests fail fast to avoid duplicated partial output |
| Client cancels | socket closes → generation stops server-side |
| Model not pulled | Ollama's error text is surfaced verbatim |

## Sizing notes (local 14B)
Committee mode = 8 sequential generations, debate = 5 — expect minutes, watch
the streamed progress. `AI_NUM_CTX=8192` fits the grounded snapshot (~12k
chars ≈ 4k tokens) plus output; raise it if you raise the snapshot caps.
