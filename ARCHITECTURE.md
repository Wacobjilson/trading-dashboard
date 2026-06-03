# Architecture

## System overview

```
                         ┌──────────────────────────────────────────────┐
                         │                  Browser                      │
                         │   Next.js (SSR/CSR) · ShadCN · Recharts        │
                         │   TanStack Query · WebSocket client            │
                         └───────────────┬───────────────┬──────────────┘
                                  HTTPS  │               │  WSS
                                         ▼               ▼
                         ┌──────────────────────────────────────────────┐
                         │              Ingress (Traefik / NGINX)         │
                         └───────────────┬───────────────┬──────────────┘
                                         │               │
                       /api/* , /ws ─────┘               └──── /  (Next.js)
                                         ▼
        ┌────────────────────────────────────────────────────────────────────┐
        │                         Go Backend (cmd/api)                          │
        │                                                                      │
        │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
        │  │  Auth    │  │  REST    │  │  WebSocket    │  │  Ingestion        │  │
        │  │  (JWT)   │  │ handlers │  │  hub (fan-out)│  │  workers          │  │
        │  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘  │
        │       │             │               │                   │            │
        │       └─────────────┴───────┬───────┴───────────────────┘            │
        │                             ▼                                        │
        │              ┌────────────────────────────┐                          │
        │              │  Market Data Provider iface │                          │
        │              │  polygon │ finnhub │ alpha   │  (pluggable)            │
        │              └────────────────────────────┘                          │
        └───────────────┬───────────────────────────┬─────────────────────────┘
                        │                            │
                        ▼                            ▼
              ┌───────────────────┐        ┌───────────────────┐
              │   PostgreSQL 16   │        │     Redis 7       │
              │  (timeseries +    │        │  cache + pub/sub  │
              │   relational)     │        │  + rate limiting  │
              └───────────────────┘        └───────────────────┘

   External feeds (HTTP/WS): Polygon.io · Finnhub · Alpha Vantage · Twelve Data
   AI provider (HTTP):        Anthropic Claude (default) · OpenAI · Gemini · Ollama · OpenRouter
```

## Backend modules (`backend/internal`)

| Package      | Responsibility                                                        |
|--------------|-----------------------------------------------------------------------|
| `config`     | Env-driven config loading + provider selection                       |
| `db`         | pgx connection pool, migration runner                                 |
| `cache`      | Redis client, helpers, pub/sub for fan-out                           |
| `auth`       | Argon2id password hashing, JWT issue/verify, middleware              |
| `models`     | Domain types + DB access (users, symbols, quotes, watchlists)        |
| `market`     | `Provider` interface + Polygon/Finnhub/AlphaVantage/mock adapters    |
| `ingest`     | Background pollers that pull quotes and publish to Redis + WS hub     |
| `ws`         | WebSocket hub: client registry, topic subscriptions, broadcast       |
| `httpapi`    | chi router, route registration, REST handlers, middleware           |

### Request flow (REST quote)

1. Client `GET /api/v1/quotes?symbols=SPY,QQQ` with `Authorization: Bearer <jwt>`.
2. `auth` middleware validates JWT.
3. Handler checks Redis (`quote:SPY`); on miss, calls the active `market.Provider`,
   writes through to Redis with a short TTL, returns JSON.

### Streaming flow (WebSocket)

1. Client connects `wss://host/ws?token=<jwt>` and sends `{"action":"subscribe","topics":["quote:SPY"]}`.
2. `ingest` workers poll/stream the provider on an interval, publish updates to the
   Redis channel `quotes` **and** directly into the in-process `ws.Hub`.
3. The hub fans messages out to every client subscribed to the matching topic.
4. Multiple backend replicas stay consistent because each subscribes to the Redis
   `quotes` channel (pub/sub), so a quote fetched by one pod reaches clients on all pods.

## Data model (Stage 1)

See [`backend/internal/db/migrations/0001_init.sql`](./backend/internal/db/migrations/0001_init.sql)
(embedded into the binary and applied automatically on startup).
Core tables: `users`, `symbols`, `quotes` (latest snapshot), `ohlcv` (timeseries,
hypertable-ready), `watchlists`, `watchlist_items`, plus stubs for `news`, `alerts`,
and `ai_summaries` that later stages flesh out.

## Pluggable provider pattern

`market.Provider` is a small interface (`Quote`, `Quotes`, `Name`). Each adapter maps a
vendor API to the common `models.Quote` shape and normalizes symbols (e.g. futures
`ES` → provider-specific continuous-contract symbol). Selection is by `MARKET_DATA_PROVIDER`
env var, else the first provider with a configured key, else the `mock` provider.

The same pattern is used for `ai.Provider` (Anthropic default) so the AI engine in
later stages is vendor-agnostic.

## Security

- Passwords hashed with Argon2id.
- Stateless JWT (HS256) access tokens; secret from `JWT_SECRET` (K8s secret in prod).
- All secrets injected via env / Kubernetes `Secret`, never baked into images.
- CORS locked to the configured frontend origin.
- Per-IP rate limiting on auth endpoints via Redis.

## Scaling notes

- Backend is stateless → scale horizontally (HPA on CPU). Redis pub/sub keeps WS
  fan-out correct across replicas.
- `ohlcv` is designed for TimescaleDB; convert to a hypertable for millions of rows.
- Hot quote reads served from Redis; Postgres handles durable + historical data.
