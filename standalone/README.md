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

**Keys (recommended — keeps them out of git):** copy the example file and fill it in:

```bash
cp keys.local.json.example keys.local.json
# then edit keys.local.json with your keys
```

`keys.local.json` is gitignored, so it never gets committed. The server loads keys
in this order per provider: **environment variable → keys.local.json → empty**.
Do **not** hardcode keys inside `quanta.py` — that file is tracked by git.

Other settings (env vars):

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
