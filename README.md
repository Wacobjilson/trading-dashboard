# Quanta — Self-Hosted Trading Intelligence Platform

A Bloomberg-Terminal-inspired, self-hostable trading dashboard for stocks, options,
futures, ETFs, forex, crypto, economic events, news, order flow, and AI market
intelligence. Built to run on Kubernetes, K3s, Talos, Proxmox, or plain Docker Compose.

> **Status: MVP (Stage 1)** — Live market dashboard, user authentication, pluggable
> market-data adapters (Polygon / Finnhub / Alpha Vantage), Postgres + Redis,
> WebSocket streaming, and full Kubernetes/Helm + Docker Compose deployment.
> See [`ROADMAP.md`](./ROADMAP.md) for what ships in later stages.

## Stack

| Layer        | Technology                                                        |
|--------------|-------------------------------------------------------------------|
| Frontend     | Next.js 14 (App Router), React 18, TypeScript, TailwindCSS, ShadCN UI, Recharts, TanStack Query/Table |
| Backend      | Go 1.22, `chi` router (REST), `gorilla/websocket` (streaming)      |
| Database     | PostgreSQL 16 (+ TimescaleDB-ready schema)                        |
| Cache/PubSub | Redis 7                                                           |
| AI           | Pluggable LLM provider — Anthropic Claude (default), OpenAI, Gemini, Ollama, OpenRouter |
| Deploy       | Docker, Docker Compose, Helm chart, raw K8s manifests (Traefik + NGINX ingress) |

## Quick start (Docker Compose)

```bash
cp .env.example .env          # fill in at least one market-data API key
docker compose up --build
```

- Frontend → http://localhost:3000
- Backend API → http://localhost:8080/api/v1
- Postgres → localhost:5432, Redis → localhost:6379

Register a user at `/register`, then log in. The dashboard streams quotes for the
core index/futures/macro instruments over WebSocket.

## Quick start (Kubernetes / Helm)

```bash
# Create the secret with your API keys + JWT secret first (see deploy/helm/README)
helm upgrade --install quanta ./deploy/helm/trading-dashboard \
  --namespace quanta --create-namespace \
  -f ./deploy/helm/trading-dashboard/values.yaml
```

Raw manifests (no Helm) live in [`deploy/k8s/`](./deploy/k8s/).

## Repository layout

```
trading-dashboard/
├── backend/        Go API + WebSocket gateway, data ingestion, auth
├── frontend/       Next.js app (Bloomberg-style terminal UI)
├── deploy/
│   ├── helm/       Helm chart
│   └── k8s/        Raw Kubernetes manifests
├── docker-compose.yml
├── ARCHITECTURE.md
└── ROADMAP.md
```

## Configuration

All config is via environment variables — see [`.env.example`](./.env.example).
At minimum set a `JWT_SECRET` and one of `POLYGON_API_KEY`, `FINNHUB_API_KEY`, or
`ALPHAVANTAGE_API_KEY`. The backend auto-selects the first configured provider, or
you can pin one with `MARKET_DATA_PROVIDER=polygon|finnhub|alphavantage`.

If no provider key is set, the backend runs in **mock mode** and serves synthetic
quotes so you can demo the full stack without any data subscription.

## License

For personal/self-hosted use. Respect the terms of service of each market-data
provider you connect.
