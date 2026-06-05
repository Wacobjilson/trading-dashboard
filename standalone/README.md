# Quanta standalone — quant swing-trading companion (Python + HTML)

A zero-dependency, single-user dashboard built to complement a main platform
(e.g. ThinkOrSwim). It answers: **where is money rotating, and where are the 50%
retracement entries?** No Docker, no Kubernetes, no database, no login — just
Python 3 (standard library only) serving one HTML page.

## Tabs

| Tab | What it shows |
|-----|---------------|
| **Signals** | The **out-of-sample-validated edge**: Connors **RSI(2) mean-reversion** on the sector ETFs. BUY when a sector is above its 200-day SMA and RSI(2) < 10; exit when price closes back above the 5-day SMA. Live per-sector state (BUY / Arming / Flat / Bear), RSI(2), the exit level, and distance to exit. |
| **Rotation** | The 11 SPDR sector ETFs ranked by relative strength vs SPY (1w/1m/3m) with an RRG-style scatter (Leading / Weakening / Lagging / Improving) — *where the money is moving*. |
| **Entries** | A **sector-ETF-only** scanner for **50% retracement setups** (daily & weekly). Swings come from an ATR-scaled **ZigZag** (real pivots). Each candidate gets a multi-factor **confluence score** (hover it for the breakdown), entry zone, ATR-buffered stop, prior-swing + 1.272-extension targets, R:R, RSI and RS-vs-SPY. |
| **Chart** | Per-symbol SVG candlestick: SMA20/50, the ZigZag swing pivots, swing high/low, Fib 38.2/50/61.8 and the shaded entry zone. Click any Rotation/Entries row to chart it. |
| **Futures 15m** | Intraday **context** for ES/NQ/RTY/YM via 15-min ETF proxies (SPY/QQQ/IWM/DIA): session VWAP, opening range, prior-day H/L, EMA9/20, RSI(2), and a 15-min chart. Real ES/NQ need a paid futures feed; this is RTH-proxy context, **not** a backtested signal. |
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

## Strategy research (`research.py`)

`research.py` is how the Signals edge was found. It fetches the sector daily bars
once, then tests a battery of documented long-only systems — Connors **RSI(2)**
mean-reversion variants (with/without the 200-SMA regime filter, different exits,
a stop), an SMA-10 pullback, and a 20-day momentum **breakout** — each split into
**TRAIN (first 60%)** and **TEST (held-out 40%)**, reported in per-trade % with PF,
win%, drawdown and per-trade Sharpe, against an equal-weight buy-&-hold benchmark.

```bash
python research.py                       # real Polygon bars (~2.5 min to fetch)
QUANTA_SYNTH_BARS=1 python research.py   # synthetic (machinery only)
```

**Result on 2yr Polygon data:** the RSI(2) family held up out-of-sample (~73% win,
PF ~2.0, ~+0.5%/trade across variants); momentum/breakout did **not** (PF 1.6, 33%
win, big drawdown). That out-of-sample RSI(2) result is what the **Signals** tab serves.
Caveats: returns are pre-slippage (idealized close fills); 2 years is a mostly-bullish
sample, so the 200-SMA regime filter stays on as the crash guardrail.

## Backtesting

`backtest.py` replays the **exact** entry logic (`analyze_bars`) bar-by-bar over
history with **no lookahead** — at each bar it only sees data up to that bar. On a
fresh "Ready" signal it enters at that bar's close, then resolves the trade against
future bars (stop vs target first; same-bar = stop; else exit after a max hold).

```bash
python backtest.py                       # daily + weekly, both directions (Polygon bars)
QUANTA_SYNTH_BARS=1 python backtest.py   # synthetic bars (no API, instant)
BT_DIR=long BT_WITH_TREND=1 python backtest.py   # only with-trend longs
BT_SWEEP=1 python backtest.py            # grid-search stop × target × min_score, ranked by expectancy
BT_STOP=fib786 BT_TGT=ext1618 python backtest.py # try a specific level scheme
BT_WF=1 BT_DIR=long python backtest.py   # walk-forward: optimize on train (first 60%), test out-of-sample
```

**Walk-forward** is the honest test: it optimizes the param grid on the first
`BT_WF_FRAC` (default 0.6) of history, locks the winner, then measures it on the
held-out remainder it never saw — alongside the default scheme as a baseline. If the
"optimized" params don't beat the default out-of-sample, the sweep was curve-fitting.
(2 years of daily bars is a small sample, so treat this as directional evidence.)

Results are in **R-multiples** (R = 1 unit of initial risk): win %, expectancy,
profit factor, total R, max drawdown, streaks, plus per-timeframe / per-direction /
per-sector breakdowns and a sample of trades. Knobs: `BT_TF`, `BT_DIR`,
`BT_WITH_TREND`, `BT_MIN_SCORE`, `BT_STOP` (`fib618`|`fib786`|`swinglow`),
`BT_TGT` (`ext1272`|`ext1618`|`prior`), and `BT_SWEEP`.

> Idealized fills (no slippage/commission), bar-high/low touch logic, conservative
> same-bar resolution. It validates the logic's *edge*, not live performance.

## Entry algorithm (transparent — not advice)

- **Swing detection:** an ATR-scaled **ZigZag** identifies real pivot highs/lows
  (the reversal threshold adapts to each ETF's volatility), then the most recent
  confirmed pivot defines the active impulse leg and its direction.
- **50% retracement (default scheme):** entry = the leg's 50% Fib; **stop just
  outside the 61.8% fib** (0.25×ATR beyond); **target = 1.272 extension**. This is
  configurable (`DEFAULT_PARAMS` in quanta.py / `BT_STOP`,`BT_TGT` in the backtest) —
  the backtest sweep showed extension targets give a far better R:R than targeting
  the prior swing.
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
