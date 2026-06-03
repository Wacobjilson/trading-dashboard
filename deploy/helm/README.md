# Helm deployment

```bash
# 1. Build & push images (or use your CI). Example with GHCR:
# The frontend image is host-agnostic (same-origin /api + /ws via ingress) — no
# build args needed. In practice the GitHub Actions workflow builds & pushes both.
docker build -t ghcr.io/your-org/quanta-backend:0.1.0 ./backend
docker build -t ghcr.io/your-org/quanta-frontend:0.1.0 ./frontend
docker push ghcr.io/your-org/quanta-backend:0.1.0
docker push ghcr.io/your-org/quanta-frontend:0.1.0

# 2. Install
helm upgrade --install quanta ./trading-dashboard \
  --namespace quanta --create-namespace \
  --set image.registry=ghcr.io \
  --set image.repository=your-org/quanta \
  --set ingress.host=quanta.example.com \
  --set ingress.corsAllowedOrigins=https://quanta.example.com \
  --set ingress.className=traefik \
  --set secret.values.JWT_SECRET="$(openssl rand -base64 48)" \
  --set secret.values.FINNHUB_API_KEY="<your-key>"
```

## Production secret handling

Don't put real keys in `values.yaml`. Either:

- Pre-create a `Secret` with keys `JWT_SECRET`, `POSTGRES_PASSWORD`, `POLYGON_API_KEY`,
  `FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`, `TWELVEDATA_API_KEY`, `ANTHROPIC_API_KEY`
  and set `--set secret.existingSecret=<name> --set secret.create=false`, or
- Use sealed-secrets / external-secrets-operator and point `secret.existingSecret` at it.

## Ingress controllers

- **Traefik** (default): WebSockets work with no extra config.
- **NGINX**: set `--set ingress.className=nginx`; the chart adds long proxy timeouts
  and HTTP/1.1 upgrade annotations for the `/ws` path.

## External Postgres / Redis

Set `postgres.enabled=false` / `redis.enabled=false` and point the backend at your
managed instances by overriding the `DATABASE_URL` / `REDIS_URL` env (edit
`templates/backend.yaml` or supply them via the secret).
