# Quanta standalone — quant swing-trading companion (Python + HTML)

A zero-dependency, single-user dashboard built to complement a main platform
(e.g. ThinkOrSwim). It answers: **where is money rotating, and where are the 50%
retracement entries?** No Docker, no Kubernetes, no database, no login — just
Python 3 (standard library only) serving one HTML page.

## Tabs

| Tab | What it shows |
|-----|---------------|
| **Rotation** | The 11 SPDR sector ETFs ranked by relative strength vs SPY (1w/1m/3m) with an RRG-style scatter (Leading / Weakening / Lagging / Improving) — *where the money is moving*. |
| **Entries** | A **sector-ETF-only** scanner for **50% retracement setups** (daily & weekly). Swings come from an ATR-scaled **ZigZag** (real pivots). Each candidate gets a multi-factor **confluence score** (hover it for the breakdown), entry zone, ATR-buffered stop, prior-swing + 1.272-extension targets, R:R, RSI and RS-vs-SPY. |
| **Chart** | Per-symbol SVG candlestick: SMA20/50, the ZigZag swing pivots, swing high/low, Fib 38.2/50/61.8 and the shaded entry zone. Click any Rotation/Entries row to chart it. |
| **Markets** | Macro overview grid (SPY, QQQ, IWM, DIA, VIX, CL, GC, US10Y, DXY). |
| **News** | Market news in chronological order (newest first), auto-categorized (Fed, Inflation, Jobs, Earnings, M&A…) with sentiment + impact. |
| **Calendar** | Economic events with **forecast / previous / actual + surprise %**, filterable by impact and currency, plus a live **countdown** to the next high-impact release. Earnings too. |

> **Data:** quotes/news/earnings from Finnhub; **historical daily bars from Polygon**
> (free tier: 2 years daily, 5 req/min — so bars warm up in the background over a few
> minutes on first launch, then cache for the day). Weekly bars are resampled from daily.
> Economic events use a free, keyless weekly feed (FairEconomy/ForexFactory).
>
> **No Polygon key?** Set `QUANTA_SYNTH_BARS=1` (or just leave it unset) to run the
> rotation/entries/chart features on **synthetic bars** so you can explore the UI.

## Entry algorithm (transparent — not advice)

- **Swing detection:** an ATR-scaled **ZigZag** identifies real pivot highs/lows
  (the reversal threshold adapts to each ETF's volatility), then the most recent
  confirmed pivot defines the active impulse leg and its direction.
- **50% retracement:** entry = the leg's 50% Fib; the zone is the 38.2–61.8% golden
  pocket. Stop = swing extreme buffered by 0.5×ATR; targets = prior swing (T1) and a
  1.272 extension (T2).
- **Confluence score (0–100)** = weighted blend of: location in the pocket (.26),
  trend alignment vs SMA20/50/200 + slope (.18), RSI posture (.12), MACD momentum
  (.10), relative strength vs SPY (.14), pullback volume (.06), reversal candle (.06),
  and reward:risk (.08). Hover the score in the Entries table for the per-factor breakdown.
- **Rotation** uses sector-minus-SPY returns: 3-month = strength axis, 1-month =
  momentum axis → Leading / Weakening / Lagging / Improving quadrants.

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
