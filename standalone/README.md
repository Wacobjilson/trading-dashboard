# Quanta standalone (Python + HTML)

The zero-dependency, single-user version. No Docker, no Kubernetes, no database,
no login. Just Python 3 (standard library only) serving one HTML dashboard.

## Run it

```bash
# Mock mode (no keys) — works instantly:
python3 quanta.py

# With real data — pass your keys as env vars (any one provider is enough):
FINNHUB_API_KEY=xxxx python3 quanta.py
# or
POLYGON_API_KEY=xxxx python3 quanta.py
```

Then open **http://localhost:8000/** in your browser.

Running it on another machine (e.g. your k3s node)? Browse to
`http://<that-machine-ip>:8000/` from any device on your network.

You can also just **double-click `index.html`** — it falls back to calling
`http://localhost:8000` (the server sends permissive CORS headers so that works).

## Configure

Either set environment variables, or edit the `API_KEYS` / settings block at the
top of [`quanta.py`](./quanta.py):

| Variable | Meaning |
|----------|---------|
| `FINNHUB_API_KEY` / `POLYGON_API_KEY` / `ALPHAVANTAGE_API_KEY` | data provider keys (first one set is used) |
| `MARKET_DATA_PROVIDER` | pin a provider: `polygon` \| `finnhub` \| `alphavantage` \| `mock` |
| `PORT` | HTTP port (default `8000`) |
| `REFRESH_SECONDS` | how often to refresh quotes (default `15`; raise it for tight free-tier limits) |

If a live quote fails for a symbol, that symbol falls back to synthetic data so the
dashboard stays fully populated (the status bar shows when mock fallback is active).

## Keep it running in the background (Linux)

```bash
nohup env FINNHUB_API_KEY=xxxx python3 quanta.py > quanta.log 2>&1 &
```

To stop: `pkill -f quanta.py`.
