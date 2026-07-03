#!/usr/bin/env python3
"""
Quanta — a quant swing-trading companion (for use alongside ThinkOrSwim).

Standalone, zero-dependency (Python standard library only). It focuses on three
things a discretionary swing trader actually wants each morning:

  1. SECTOR ROTATION — where the money is moving. Relative strength of the 11
     SPDR sector ETFs vs SPY, with RRG-style Leading/Weakening/Lagging/Improving
     quadrants and 1w/1m/3m relative performance.
  2. ENTRIES — a scanner that finds 50% retracement setups on the DAILY and
     WEEKLY timeframe: recent swing high/low, Fibonacci levels, the entry zone
     (golden pocket), suggested stop/target, R:R, and an entry-quality score.
  3. CHARTS — per-symbol candlestick with SMAs, swing levels, fib lines and the
     entry zone shaded, so you can eyeball the setup before pulling it up in ToS.

Plus the macro overview, news, and an economic calendar for context.

Data:
  * Quotes      — Finnhub / Polygon / Alpha Vantage (or mock).
  * Daily bars  — Polygon aggregates (free tier: 2yr daily, 5 req/min). Weekly is
                  resampled from daily. Falls back to synthetic bars if no
                  Polygon key (or set QUANTA_SYNTH_BARS=1 to force a demo).
  * News        — Finnhub. Economic calendar — free FairEconomy/ForexFactory feed.

Run:  python3 quanta.py   →   http://localhost:8000/
Keys: copy keys.local.json.example -> keys.local.json (gitignored) or use env vars.
"""

import datetime as dt
import json
import math
import os
import random
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# ─────────────────────────────────────────────────────────────────────────────
# Config / keys
# ─────────────────────────────────────────────────────────────────────────────
def _load_local_keys():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.local.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


_LOCAL_KEYS = _load_local_keys()


def _key(name):
    return os.environ.get(name.upper() + "_API_KEY") or _LOCAL_KEYS.get(name, "")


def _envbool(name, default=False):
    v = os.environ.get(name, "")
    if v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


API_KEYS = {"polygon": _key("polygon"), "finnhub": _key("finnhub"), "alphavantage": _key("alphavantage")}
PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "").lower()
PORT = int(os.environ.get("PORT", "8000"))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "20"))
FORCE_SYNTH = _envbool("QUANTA_SYNTH_BARS", False)

# ─────────────────────────────────────────────────────────────────────────────
# Universes
# ─────────────────────────────────────────────────────────────────────────────
# Macro overview (Markets tab). Futures use liquid ETF proxies for free tiers.
INSTRUMENTS = [
    ("SPY", "S&P 500 ETF", "etf", {"polygon": "SPY", "finnhub": "SPY", "alphavantage": "SPY"}),
    ("QQQ", "Nasdaq 100 ETF", "etf", {"polygon": "QQQ", "finnhub": "QQQ", "alphavantage": "QQQ"}),
    ("IWM", "Russell 2000 ETF", "etf", {"polygon": "IWM", "finnhub": "IWM", "alphavantage": "IWM"}),
    ("DIA", "Dow Jones ETF", "etf", {"polygon": "DIA", "finnhub": "DIA", "alphavantage": "DIA"}),
    ("VIX", "Volatility Index", "index", {"polygon": "I:VIX", "finnhub": "^VIX", "alphavantage": "VIXY"}),
    ("CL", "Crude Oil (USO)", "future", {"polygon": "USO", "finnhub": "USO", "alphavantage": "USO"}),
    ("GC", "Gold (GLD)", "future", {"polygon": "GLD", "finnhub": "GLD", "alphavantage": "GLD"}),
    ("US10Y", "US 10Y Yield", "rate", {"polygon": "I:TNX", "finnhub": "^TNX", "alphavantage": "IEF"}),
    ("DXY", "US Dollar Index", "index", {"polygon": "I:DXY", "finnhub": "^DXY", "alphavantage": "UUP"}),
]

# The 11 SPDR sector ETFs + SPY benchmark.
BENCH = "SPY"
SECTORS = [
    ("XLK", "Technology"), ("XLC", "Communication Svcs"), ("XLY", "Consumer Discretionary"),
    ("XLF", "Financials"), ("XLV", "Health Care"), ("XLI", "Industrials"),
    ("XLE", "Energy"), ("XLB", "Materials"), ("XLP", "Consumer Staples"),
    ("XLU", "Utilities"), ("XLRE", "Real Estate"),
]
SECTOR_NAME = dict(SECTORS)

# Extra tickers to scan for entries (override via SCREENER_SYMBOLS).
WATCHLIST = [s.strip().upper() for s in os.environ.get(
    "SCREENER_SYMBOLS", "AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,JPM,NFLX").split(",") if s.strip()]

# Everything we keep historical bars for.
BAR_UNIVERSE = []
for _s in [BENCH, "QQQ", "IWM"] + [s for s, _ in SECTORS] + WATCHLIST:
    if _s not in BAR_UNIVERSE:
        BAR_UNIVERSE.append(_s)

SEED_PRICES = {"SPY": 545, "QQQ": 470, "IWM": 205, "DIA": 395, "VIX": 14.2, "CL": 78.5, "GC": 2350,
               "US10Y": 4.35, "DXY": 104.8, "XLK": 230, "XLC": 100, "XLY": 200, "XLF": 48, "XLV": 145,
               "XLI": 135, "XLE": 92, "XLB": 90, "XLP": 80, "XLU": 72, "XLRE": 40}

FINNHUB = "https://finnhub.io/api/v1"


def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "quanta-standalone"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


_cache, _cache_lock = {}, threading.Lock()


def cache_get(key, ttl):
    with _cache_lock:
        item = _cache.get(key)
    return item[1] if item and (time.time() - item[0]) < ttl else None


def cache_set(key, value):
    with _cache_lock:
        _cache[key] = (time.time(), value)


# ─────────────────────────────────────────────────────────────────────────────
# Quote providers (Markets tab)
# ─────────────────────────────────────────────────────────────────────────────
def active_provider():
    if PROVIDER in ("polygon", "finnhub", "alphavantage", "mock"):
        return PROVIDER
    for name in ("finnhub", "polygon", "alphavantage"):
        if API_KEYS.get(name):
            return name
    return "mock"


def quote_finnhub(sym, vendor):
    url = "%s/quote?symbol=%s&token=%s" % (FINNHUB, urllib.parse.quote(vendor), urllib.parse.quote(API_KEYS["finnhub"]))
    d = http_get_json(url)
    if not d or (d.get("c", 0) == 0 and d.get("pc", 0) == 0):
        raise ValueError("empty finnhub quote")
    return {"last": d.get("c", 0.0), "change": d.get("d", 0.0), "changePercent": d.get("dp", 0.0),
            "open": d.get("o", 0.0), "high": d.get("h", 0.0), "low": d.get("l", 0.0),
            "prevClose": d.get("pc", 0.0), "volume": 0, "atr": d.get("h", 0.0) - d.get("l", 0.0)}


def quote_alphavantage(sym, vendor):
    url = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=%s&apikey=%s" % (
        urllib.parse.quote(vendor), urllib.parse.quote(API_KEYS["alphavantage"]))
    d = http_get_json(url).get("Global Quote", {})
    if not d.get("05. price"):
        raise ValueError("empty alphavantage quote")
    f = lambda k: float(d.get(k, 0) or 0)
    return {"last": f("05. price"), "change": f("09. change"),
            "changePercent": float((d.get("10. change percent", "0") or "0").replace("%", "")),
            "open": f("02. open"), "high": f("03. high"), "low": f("04. low"),
            "prevClose": f("08. previous close"), "volume": int(f("06. volume")), "atr": f("03. high") - f("04. low")}


def quote_polygon(sym, vendor):
    key = urllib.parse.quote(API_KEYS["polygon"])
    if vendor.startswith("I:"):
        url = "https://api.polygon.io/v3/snapshot/indices?ticker=%s&apiKey=%s" % (urllib.parse.quote(vendor), key)
        res = http_get_json(url).get("results", [])
        if not res:
            raise ValueError("empty polygon index")
        r = res[0]; s = r.get("session", {})
        return {"last": r.get("value", 0.0), "change": s.get("change", 0.0), "changePercent": s.get("change_percent", 0.0),
                "open": s.get("open", 0.0), "high": s.get("high", 0.0), "low": s.get("low", 0.0),
                "prevClose": s.get("previous_close", 0.0), "volume": 0, "atr": s.get("high", 0.0) - s.get("low", 0.0)}
    url = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/%s?apiKey=%s" % (urllib.parse.quote(vendor), key)
    t = http_get_json(url).get("ticker", {})
    day, prev, lt = t.get("day", {}), t.get("prevDay", {}), t.get("lastTrade", {})
    return {"last": lt.get("p") or day.get("c", 0.0), "change": t.get("todaysChange", 0.0),
            "changePercent": t.get("todaysChangePerc", 0.0), "open": day.get("o", 0.0), "high": day.get("h", 0.0),
            "low": day.get("l", 0.0), "prevClose": prev.get("c", 0.0), "volume": int(day.get("v", 0)),
            "atr": day.get("h", 0.0) - day.get("l", 0.0)}


_mock_q = {}


def quote_mock(sym, vendor):
    st = _mock_q.get(sym)
    if st is None:
        base = SEED_PRICES.get(sym, 100.0)
        st = {"last": base, "pc": base * (1 - (random.random() - .5) * .01), "o": base, "h": base, "l": base, "v": random.randint(8_000_000, 40_000_000)}
        _mock_q[sym] = st
    st["last"] = max(.01, st["last"] + (random.random() - .5) * .001 * st["last"])
    st["h"] = max(st["h"], st["last"]); st["l"] = min(st["l"], st["last"]); st["v"] += random.randint(0, 200_000)
    r2 = lambda x: round(x, 2)
    return {"last": r2(st["last"]), "prevClose": r2(st["pc"]), "open": r2(st["o"]), "high": r2(st["h"]), "low": r2(st["l"]),
            "volume": st["v"], "change": r2(st["last"] - st["pc"]), "changePercent": r2((st["last"] - st["pc"]) / st["pc"] * 100),
            "atr": r2(st["last"] * .012)}


QUOTE_FNS = {"finnhub": quote_finnhub, "alphavantage": quote_alphavantage, "polygon": quote_polygon, "mock": quote_mock}
_quotes_lock, _quotes_cache, _status = threading.Lock(), [], {"provider": active_provider(), "updated": 0}


def quotes_loop():
    provider = active_provider(); fn = QUOTE_FNS[provider]
    while True:
        out = []
        for sym, name, klass, vendors in INSTRUMENTS:
            try:
                q = fn(sym, vendors.get(provider, sym)); src = provider
            except Exception:
                q = quote_mock(sym, sym); src = "mock"
            q.update({"symbol": sym, "name": name, "assetClass": klass, "source": src})
            out.append(q)
            if provider == "alphavantage":
                time.sleep(13)
        with _quotes_lock:
            global _quotes_cache
            _quotes_cache = out; _status["updated"] = int(time.time())
        time.sleep(REFRESH_SECONDS)


# ─────────────────────────────────────────────────────────────────────────────
# Historical bars (Polygon aggregates) + synthetic fallback
# ─────────────────────────────────────────────────────────────────────────────
_bars = {}            # symbol -> list[{t,o,h,l,c,v}] (daily, ascending)
_bars_meta = {}       # symbol -> {"updated": ts, "source": "polygon"|"synth"}
_bars_lock = threading.Lock()


def fetch_polygon_daily(symbol, days=740):
    to = dt.date.today()
    frm = to - dt.timedelta(days=days)
    url = ("https://api.polygon.io/v2/aggs/ticker/%s/range/1/day/%s/%s?adjusted=true&sort=asc&limit=50000&apiKey=%s"
           % (urllib.parse.quote(symbol), frm.isoformat(), to.isoformat(), urllib.parse.quote(API_KEYS["polygon"])))
    res = http_get_json(url).get("results") or []
    if not res:
        raise ValueError("no polygon aggregates for %s" % symbol)
    return [{"t": r["t"], "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r.get("v", 0)} for r in res]


def synth_daily(symbol, n=520):
    """Deterministic-ish synthetic daily bars with trend + swings, for demo/fallback."""
    rnd = random.Random(hash(symbol) & 0xffffffff)
    price = SEED_PRICES.get(symbol, 50 + rnd.random() * 250)
    drift = (rnd.random() - 0.45) * 0.0008
    bars = []
    today = dt.datetime.now(dt.timezone.utc)
    for i in range(n):
        # cyclical component to create real swing highs/lows
        cycle = math.sin(i / 22.0) * 0.004 + math.sin(i / 60.0) * 0.006
        ret = drift + cycle + (rnd.random() - 0.5) * 0.018
        o = price
        c = max(1.0, price * (1 + ret))
        hi = max(o, c) * (1 + rnd.random() * 0.008)
        lo = min(o, c) * (1 - rnd.random() * 0.008)
        ts = int((today - dt.timedelta(days=(n - i))).timestamp() * 1000)
        bars.append({"t": ts, "o": round(o, 2), "h": round(hi, 2), "l": round(lo, 2),
                     "c": round(c, 2), "v": rnd.randint(5_000_000, 50_000_000)})
        price = c
    return bars


def load_bars(symbol):
    """Fetch daily bars for a symbol (polygon, else synthetic). Returns (bars, source)."""
    if not FORCE_SYNTH and API_KEYS.get("polygon"):
        try:
            return fetch_polygon_daily(symbol), "polygon"
        except Exception:
            pass
    return synth_daily(symbol), "synth"


def get_bars(symbol):
    with _bars_lock:
        return _bars.get(symbol)


def bars_loop():
    """Background warmer. Daily bars only change once/day, so refresh slowly and
    pace Polygon calls to respect the 5 req/min free-tier limit."""
    use_polygon = bool(API_KEYS.get("polygon")) and not FORCE_SYNTH
    while True:
        for symbol in BAR_UNIVERSE:
            meta = _bars_meta.get(symbol)
            if meta and (time.time() - meta["updated"]) < 6 * 3600:
                continue
            bars, src = load_bars(symbol)
            with _bars_lock:
                _bars[symbol] = bars
                _bars_meta[symbol] = {"updated": time.time(), "source": src}
            if use_polygon and src == "polygon":
                time.sleep(12)  # ≈5 calls/min
        time.sleep(300)


def warm_status():
    have = sum(1 for s in BAR_UNIVERSE if s in _bars)
    src = _bars_meta.get(BENCH, {}).get("source", "—")
    return {"have": have, "total": len(BAR_UNIVERSE), "source": src, "ready": have >= len(BAR_UNIVERSE)}


# ─────────────────────────────────────────────────────────────────────────────
# Analytics: SMA, returns, swing detection, Fibonacci, entry setup
# ─────────────────────────────────────────────────────────────────────────────
def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def pct_return(closes, n):
    if len(closes) > n and closes[-1 - n]:
        return (closes[-1] / closes[-1 - n] - 1) * 100
    return None


def resample_weekly(daily):
    """Aggregate daily bars into weekly OHLCV by ISO (year, week)."""
    weeks = {}
    order = []
    for b in daily:
        d = dt.datetime.fromtimestamp(b["t"] / 1000, dt.timezone.utc).isocalendar()
        key = (d[0], d[1])
        w = weeks.get(key)
        if w is None:
            weeks[key] = {"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"]}
            order.append(key)
        else:
            w["h"] = max(w["h"], b["h"]); w["l"] = min(w["l"], b["l"]); w["c"] = b["c"]; w["v"] += b["v"]; w["t"] = b["t"]
    return [weeks[k] for k in order]


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _stdev(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


FIB = [0.236, 0.382, 0.5, 0.618, 0.786]

# Default trade-level scheme: enter at the 50% retracement, stop just outside the
# 61.8% fib, target the 1.272 extension. (Backtest can sweep these.)
DEFAULT_PARAMS = {"stop_mode": "fib618", "stop_buf": 0.25, "target_mode": "ext1272", "min_score": 55}


def trade_levels(direction, levels, HH, LL, rng, av, p):
    """Compute (entry, stop, target) for a 50%-entry setup given a level scheme.

    stop_mode: 'fib618' | 'fib786' | 'swinglow'  (stop_buf = ATR multiple beyond it)
    target_mode: 'ext1272' | 'ext1618' | 'prior' (prior = the swing extreme)"""
    fibkey = {"fib618": "0.618", "fib786": "0.786"}.get(p["stop_mode"], "0.618")
    buf = p.get("stop_buf", 0.25) * av
    entry = levels["0.5"]
    if direction == "long":
        stop = (LL if p["stop_mode"] == "swinglow" else levels[fibkey]) - buf
        target = HH if p["target_mode"] == "prior" else LL + (1.618 if p["target_mode"] == "ext1618" else 1.272) * rng
    else:
        stop = (HH if p["stop_mode"] == "swinglow" else levels[fibkey]) + buf
        target = LL if p["target_mode"] == "prior" else HH - (1.618 if p["target_mode"] == "ext1618" else 1.272) * rng
    return round(entry, 2), round(stop, 2), round(target, 2)


# ── Indicators ───────────────────────────────────────────────────────────────
def ema_series(vals, n):
    if len(vals) < n:
        return [None] * len(vals)
    k = 2.0 / (n + 1)
    out = [None] * (n - 1)
    e = sum(vals[:n]) / n
    out.append(e)
    for v in vals[n:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(closes, n=14):
    if len(closes) <= n:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    ag = sum(d for d in deltas[:n] if d > 0) / n
    al = -sum(d for d in deltas[:n] if d < 0) / n
    for d in deltas[n:]:
        ag = (ag * (n - 1) + (d if d > 0 else 0)) / n
        al = (al * (n - 1) + (-d if d < 0 else 0)) / n
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def atr(bars, n=14):
    if len(bars) <= n:
        return None
    trs = [max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i - 1]["c"]),
               abs(bars[i]["l"] - bars[i - 1]["c"])) for i in range(1, len(bars))]
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def macd_hist(closes):
    """Return (hist_now, hist_prev) for MACD(12,26,9)."""
    if len(closes) < 35:
        return None, None
    e12, e26 = ema_series(closes, 12), ema_series(closes, 26)
    line = [(a - b) if (a is not None and b is not None) else None for a, b in zip(e12, e26)]
    vals = [m for m in line if m is not None]
    sig = ema_series(vals, 9)
    sigfull = [None] * (len(line) - len(sig)) + sig
    hist = [(m - s) if (m is not None and s is not None) else None for m, s in zip(line, sigfull)]
    hv = [h for h in hist if h is not None]
    if len(hv) < 2:
        return None, None
    return hv[-1], hv[-2]


# ── ZigZag swing detection (ATR-scaled reversal threshold) ───────────────────
def zigzag(bars, pct):
    """Return confirmed pivots [(idx, price, 'H'|'L')] using a % reversal filter."""
    n = len(bars)
    if n < 3:
        return []
    pivots = []
    last_high, last_high_i = bars[0]["h"], 0
    last_low, last_low_i = bars[0]["l"], 0
    dirn = 0
    for i in range(1, n):
        h, l = bars[i]["h"], bars[i]["l"]
        if dirn > 0:
            if h > last_high:
                last_high, last_high_i = h, i
            elif l <= last_high * (1 - pct):
                pivots.append((last_high_i, last_high, "H")); dirn = -1; last_low, last_low_i = l, i
        elif dirn < 0:
            if l < last_low:
                last_low, last_low_i = l, i
            elif h >= last_low * (1 + pct):
                pivots.append((last_low_i, last_low, "L")); dirn = 1; last_high, last_high_i = h, i
        else:
            if h > last_high:
                last_high, last_high_i = h, i
            if l < last_low:
                last_low, last_low_i = l, i
            if l <= last_high * (1 - pct):
                pivots.append((last_high_i, last_high, "H")); dirn = -1; last_low, last_low_i = l, i
            elif h >= last_low * (1 + pct):
                pivots.append((last_low_i, last_low, "L")); dirn = 1; last_high, last_high_i = h, i
    return pivots


def active_leg(bars, pivots):
    """From the last confirmed pivot, define the current impulse leg + direction."""
    if pivots:
        li, lp, lt = pivots[-1]
        seg = bars[li:]
        if lt == "L":  # turned up at the low → current upswing; high = max since
            hi_rel = max(range(len(seg)), key=lambda k: seg[k]["h"])
            return lp, seg[hi_rel]["h"], li, li + hi_rel, "long"
        lo_rel = min(range(len(seg)), key=lambda k: seg[k]["l"])
        return seg[lo_rel]["l"], lp, li + lo_rel, li, "short"
    # fallback: window extremes
    win = bars[-90:] if len(bars) >= 90 else bars
    hi_i = max(range(len(win)), key=lambda i: win[i]["h"])
    lo_i = min(range(len(win)), key=lambda i: win[i]["l"])
    base = len(bars) - len(win)
    if lo_i <= hi_i:
        return win[lo_i]["l"], win[hi_i]["h"], base + lo_i, base + hi_i, "long"
    return win[lo_i]["l"], win[hi_i]["h"], base + lo_i, base + hi_i, "short"


def _gauss(x, mu, w):
    return math.exp(-((x - mu) / w) ** 2)


def zigzag_pct(bars, tf):
    av = atr(bars, 14) or (bars[-1]["c"] * 0.02)
    return min(0.15, max(0.02, (av / bars[-1]["c"]) * (3.0 if tf == "daily" else 4.0)))


def pivots_for(symbol, tf="daily"):
    daily = get_bars(symbol)
    if not daily:
        return [], []
    bars = resample_weekly(daily) if tf == "weekly" else daily
    return bars, zigzag(bars, zigzag_pct(bars, tf))


def analyze_bars(bars, symbol="", tf="daily", spy_closes=None, params=None):
    """PURE setup analysis on a given bar list (no global state, no lookahead) —
    used by both the live endpoints and the backtester.

    ATR-scaled ZigZag finds real swing pivots; entry is the 50% retracement of the
    most recent impulse leg; stop/target follow `params` (default: stop just outside
    the 61.8% fib, target the 1.272 extension). The confluence score blends pocket
    location, trend alignment, RSI, MACD momentum, relative strength vs SPY, pullback
    volume, a reversal-candle check, and reward:risk."""
    p = params or DEFAULT_PARAMS
    if not bars or len(bars) < 40:
        return {"symbol": symbol, "tf": tf, "ok": False, "reason": "not enough bars"}

    closes = [b["c"] for b in bars]
    vols = [b.get("v", 0) for b in bars]
    close = closes[-1]
    pivots = zigzag(bars, zigzag_pct(bars, tf))

    LL, HH, _lo_i, _hi_i, direction = active_leg(bars, pivots)
    rng = max(HH - LL, 1e-9)
    if direction == "long":
        levels = {str(p): round(HH - p * rng, 2) for p in FIB}
        depth = (HH - close) / rng
    else:
        levels = {str(p): round(LL + p * rng, 2) for p in FIB}
        depth = (close - LL) / rng
    fib50 = round((HH + LL) / 2.0, 2)
    dist50 = (close - fib50) / fib50 * 100

    s20, s50, s200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    s50_prev = sma(closes[:-5], 50) if len(closes) > 55 else None
    if s50 and s200:
        trend = "up" if close > s50 > s200 else "down" if close < s50 < s200 else "side"
    elif s50:
        trend = "up" if close > s50 else "down"
    else:
        trend = "side"

    av = atr(bars, 14) or rng * 0.05
    rs_val = rsi(closes, 14)
    hist, hist_prev = macd_hist(closes)
    n3, n1 = (63, 21) if tf == "daily" else (13, 4)

    def _rs(n):
        a = pct_return(closes, n)
        b = pct_return(spy_closes, n) if spy_closes else None
        return round(a - b, 2) if (a is not None and b is not None) else None

    rs3m, rs1m = _rs(n3), _rs(n1)
    avg20 = sum(vols[-20:]) / 20 if len(vols) >= 20 else (sum(vols) / len(vols) if vols else 0)
    avg5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else avg20

    entry, stop, target = trade_levels(direction, levels, HH, LL, rng, av, p)
    target2 = round(HH if direction == "long" else LL, 2)   # prior swing, for reference
    risk = abs(entry - stop)
    rr = round(abs(target - entry) / risk, 2) if risk > 0 else None

    loc = max(0.0, 1 - abs(depth - 0.5) / 0.5)
    if direction == "long":
        tr = sum([close > (s20 or close), close > (s50 or close), (s50 or 0) > (s200 or 0),
                  bool(s50_prev and s50 and s50 > s50_prev)]) / 4.0
        mom = _gauss(rs_val, 43, 18) if rs_val is not None else 0.4
        mac = (0.6 if (hist is not None and hist_prev is not None and hist > hist_prev) else 0.0) + (0.4 if (hist is not None and hist > 0) else 0.0)
        rsc = clamp((0.5 + (rs3m or 0) / 12.0), 0, 1)
        candle = 1.0 if bars[-1]["c"] >= bars[-1]["o"] else 0.4
    else:
        tr = sum([close < (s20 or close), close < (s50 or close), (s50 or 1e9) < (s200 or 1e9),
                  bool(s50_prev and s50 and s50 < s50_prev)]) / 4.0
        mom = _gauss(rs_val, 57, 18) if rs_val is not None else 0.4
        mac = (0.6 if (hist is not None and hist_prev is not None and hist < hist_prev) else 0.0) + (0.4 if (hist is not None and hist < 0) else 0.0)
        rsc = clamp((0.5 - (rs3m or 0) / 12.0), 0, 1)
        candle = 1.0 if bars[-1]["c"] <= bars[-1]["o"] else 0.4
    volsc = 1.0 if (avg20 and avg5 < avg20) else 0.4
    rrsc = min(1.0, (rr or 0) / 3.0)

    weights = {"location": 0.26, "trend": 0.18, "momentum": 0.12, "macd": 0.10,
               "rs": 0.14, "volume": 0.06, "candle": 0.06, "rr": 0.08}
    subs = {"location": loc, "trend": tr, "momentum": mom, "macd": mac,
            "rs": rsc, "volume": volsc, "candle": candle, "rr": rrsc}
    score = round(clamp(100 * sum(weights[k] * subs[k] for k in weights)), 1)

    in_pocket = 0.382 <= depth <= 0.618
    status = "Ready" if (in_pocket and score >= p["min_score"]) else ("Approaching" if 0.25 <= depth <= 0.75 else "Extended")
    bias = "with-trend" if (direction == "long" and trend == "up") or (direction == "short" and trend == "down") else "counter-trend"
    label = "%s %s pullback to 50%%%s" % (("Bullish" if direction == "long" else "Bearish"), bias,
                                          " · RS+" if (rs3m or 0) > 0 else " · RS-")
    return {
        "symbol": symbol, "name": SECTOR_NAME.get(symbol, ""), "tf": tf, "ok": True,
        "direction": direction, "trend": trend, "status": status, "bias": bias, "label": label,
        "price": round(close, 2), "swingHigh": round(HH, 2), "swingLow": round(LL, 2),
        "fib50": fib50, "depth": round(depth, 3), "dist50": round(dist50, 2),
        "entry": round(entry, 2), "zoneHi": levels["0.382"], "zoneLo": levels["0.618"],
        "stop": stop, "target": target, "target2": target2, "rr": rr,
        "score": score, "subScores": {k: round(subs[k] * 100) for k in subs},
        "rsi": round(rs_val, 1) if rs_val is not None else None,
        "macdHist": round(hist, 3) if hist is not None else None,
        "atr": round(av, 2), "rs3m": rs3m, "rs1m": rs1m,
        "sma20": round(s20, 2) if s20 else None, "sma50": round(s50, 2) if s50 else None,
        "sma200": round(s200, 2) if s200 else None,
        "fibLevels": levels, "barsCount": len(bars),
    }


def _tf_closes(symbol, tf):
    daily = get_bars(symbol)
    if not daily:
        return None
    bars = resample_weekly(daily) if tf == "weekly" else daily
    return [b["c"] for b in bars]


def analyze(symbol, tf="daily"):
    """Live wrapper: pull cached bars for symbol + SPY, then run analyze_bars."""
    daily = get_bars(symbol)
    if not daily:
        return {"symbol": symbol, "tf": tf, "ok": False, "reason": "warming up / no data"}
    bars = resample_weekly(daily) if tf == "weekly" else daily
    return analyze_bars(bars, symbol, tf, _tf_closes(BENCH, tf))


def build_entries(symbols, tf="daily"):
    rows = [a for a in (analyze(s, tf) for s in symbols) if a.get("ok")]
    rank = {"Ready": 0, "Approaching": 1, "Extended": 2}
    rows.sort(key=lambda r: (rank.get(r["status"], 3), -r["score"]))
    return {"tf": tf, "rows": rows, "warm": warm_status()}


# ─────────────────────────────────────────────────────────────────────────────
# Sector rotation (relative strength vs SPY + RRG-style quadrants)
# ─────────────────────────────────────────────────────────────────────────────
def rotation():
    spy = get_bars(BENCH)
    out = {"warm": warm_status(), "sectors": [], "bench": BENCH}
    if not spy:
        return out
    spc = [b["c"] for b in spy]

    def rel(closes, n):
        a, b = pct_return(closes, n), pct_return(spc, n)
        return round(a - b, 2) if (a is not None and b is not None) else None

    for sym, name in SECTORS:
        bars = get_bars(sym)
        if not bars:
            out["sectors"].append({"symbol": sym, "name": name, "warming": True})
            continue
        c = [b["c"] for b in bars]
        r1w, r1m, r3m = rel(c, 5), rel(c, 21), rel(c, 63)
        r6m, r1y = rel(c, 126), rel(c, 252)
        ratio = r3m if r3m is not None else 0.0     # x-axis: 3-month relative strength
        mom = r1m if r1m is not None else 0.0        # y-axis: 1-month relative momentum
        quad = ("Leading" if ratio >= 0 and mom >= 0 else "Weakening" if ratio >= 0 and mom < 0
                else "Improving" if ratio < 0 and mom >= 0 else "Lagging")
        s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
        # volatility-adjusted 3-month return (Sharpe-ish: abs return / annualized vol)
        rets = [c[i] / c[i - 1] - 1 for i in range(max(1, len(c) - 63), len(c))]
        vol_ann = _stdev(rets) * (252 ** 0.5)
        abs3m = pct_return(c, 63)
        vol_adj = round((abs3m / 100) / vol_ann, 2) if (vol_ann and abs3m is not None) else None
        vols = [b.get("v", 0) for b in bars]
        v20 = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else None
        rel_vol = round(vols[-1] / v20, 2) if v20 else None
        out["sectors"].append({
            "symbol": sym, "name": name, "price": round(c[-1], 2),
            "chg1d": round(pct_return(c, 1) or 0, 2), "rs1w": r1w, "rs1m": r1m, "rs3m": r3m,
            "rs6m": r6m, "rs1y": r1y,
            "rsRatio": round(ratio, 2), "rsMom": round(mom, 2), "quadrant": quad,
            "trend": "up" if (s50 and c[-1] > s50) else "down",
            "above20": bool(s20 and c[-1] > s20), "above50": bool(s50 and c[-1] > s50),
            "above200": bool(s200 and c[-1] > s200), "volAdj": vol_adj, "relVol": rel_vol,
        })
    ranked = [s for s in out["sectors"] if s.get("rs3m") is not None]
    ranked.sort(key=lambda s: s["rs3m"], reverse=True)
    out["sectors"] = ranked + [s for s in out["sectors"] if s.get("rs3m") is None]
    out["leaders"] = [s["symbol"] for s in ranked[:3]]
    out["laggards"] = [s["symbol"] for s in ranked[-3:]][::-1]
    # Rotation model portfolio (research.py, out-of-sample survivor): hold the top-3
    # sectors by 1-MONTH RS vs SPY, rebalance monthly. TRAIN +1.40%/trade PF 2.88 |
    # TEST +2.51%/trade PF 2.92, 67% win, n=30 — but a small sample: candidate edge,
    # weaker statistical footing than the RSI(2) signal. Longer lookbacks (3m/6m)
    # decayed out-of-sample, so this stays honest-labeled.
    by_1m = sorted([s for s in out["sectors"] if s.get("rs1m") is not None],
                   key=lambda s: s["rs1m"], reverse=True)
    if by_1m:
        out["model"] = {
            "holdings": [s["symbol"] for s in by_1m[:3]],
            "rule": "Hold the top-3 sectors by 1-month RS vs SPY; rebalance monthly.",
            "stats": {"win": 66.7, "pf": 2.92, "avg": 2.51, "trades": 30},
            "caveat": "out-of-sample survivor, but only 30 test trades — candidate edge, size accordingly",
        }
    if ranked:
        quads = {}
        for s in ranked:
            quads[s["quadrant"]] = quads.get(s["quadrant"], 0) + 1
        rs1ms = [s["rs1m"] for s in ranked if s.get("rs1m") is not None]
        # ewMinusSpy1m = avg sector 1m return minus SPY's (equal-weight vs cap-weight
        # proxy at the sector level): positive = broad participation, negative = narrow.
        out["breadth"] = {
            "n": len(ranked),
            "above20": sum(1 for s in ranked if s["above20"]),
            "above50": sum(1 for s in ranked if s["above50"]),
            "above200": sum(1 for s in ranked if s["above200"]),
            "quadrants": quads,
            "ewMinusSpy1m": round(sum(rs1ms) / len(rs1ms), 2) if rs1ms else None,
        }
    return out


# Out-of-sample validated stats for the RSI(2) mean-reversion edge (from research.py
# on 2yr Polygon daily bars; TEST = held-out last 40%). Shown in the UI for honesty.
RSI2_EDGE = {"win": 74.7, "pf": 2.05, "avg": 0.48, "trades": 87,
             "rule": "Buy when sector > 200-day SMA and RSI(2) < 10; exit when close > 5-day SMA."}


def signals():
    """RSI(2) mean-reversion signals per sector ETF (the out-of-sample-validated edge).

    BUY  = bull regime (close > SMA200) AND RSI(2) < 10  → enter near the close.
    EXIT = close > SMA5  → take the bounce.
    """
    out = {"warm": warm_status(), "edge": RSI2_EDGE, "sectors": []}
    for sym, name in SECTORS:
        bars = get_bars(sym)
        if not bars or len(bars) < 200:
            out["sectors"].append({"symbol": sym, "name": name, "warming": True})
            continue
        c = [b["c"] for b in bars]
        close = c[-1]
        s5, s200 = sma(c, 5), sma(c, 200)
        r2 = rsi(c, 2)
        bull = bool(s200 and close > s200)
        below5 = bool(s5 and close < s5)
        if bull and r2 is not None and r2 < 10:
            sig, rank = "BUY", 0
        elif bull and r2 is not None and r2 < 20 and below5:
            sig, rank = "Arming", 1
        elif not bull:
            sig, rank = "Bear — stand aside", 3
        else:
            sig, rank = "Flat", 2
        # Live overlay: provisional RSI(2) "if today closed right now" from the live
        # quote (replaces today's partial bar if the cached daily bars already have it).
        lp = get_live(sym, 300)
        live_px = chg_live = r2_live = None
        if lp and lp.get("last"):
            live_px, chg_live = lp["last"], lp.get("changePercent")
            last_day = dt.datetime.fromtimestamp(bars[-1]["t"] / 1000, dt.timezone.utc).date()
            base = c[:-1] if last_day >= dt.date.today() else c
            r2_live = rsi(base + [live_px], 2)
        out["sectors"].append({
            "symbol": sym, "name": name, "price": round(close, 2),
            "rsi2": round(r2, 1) if r2 is not None else None,
            "priceLive": round(live_px, 2) if live_px else None,
            "chgLive": round(chg_live, 2) if chg_live is not None else None,
            "rsi2Live": round(r2_live, 1) if r2_live is not None else None,
            "sma5": round(s5, 2) if s5 else None, "sma200": round(s200, 2) if s200 else None,
            "regime": "bull" if bull else "bear", "signal": sig, "rank": rank,
            "distExit": round((close / s5 - 1) * 100, 2) if s5 else None,
        })
    out["sectors"].sort(key=lambda r: (r.get("rank", 9), r.get("rsi2") if r.get("rsi2") is not None else 999))
    return out


def chart_data(symbol, tf="daily", n=120):
    bars, pivots = pivots_for(symbol, tf)
    if not bars:
        return {"symbol": symbol, "tf": tf, "ok": False, "reason": "warming up"}
    a = analyze(symbol, tf)
    show = bars[-n:]
    offset = len(bars) - len(show)
    closes = [b["c"] for b in bars]

    def sma_series(period):
        return [round(sum(closes[i - period + 1:i + 1]) / period, 2) if i >= period - 1 else None
                for i in range(offset, len(bars))]

    # pivots within the shown window (x = index in show)
    pv = [{"x": i - offset, "price": round(p, 2), "type": t} for (i, p, t) in pivots if i >= offset]
    return {"symbol": symbol, "tf": tf, "ok": a.get("ok", False), "setup": a,
            "bars": show, "sma20": sma_series(20), "sma50": sma_series(50), "pivots": pv,
            "source": _bars_meta.get(symbol, {}).get("source", "?")}


# ─────────────────────────────────────────────────────────────────────────────
# Futures (15-min) via liquid ETF proxies — intraday CONTEXT (VWAP / ORB / EMAs).
# NOTE: real ES/NQ/etc. need a paid futures feed; these proxies are RTH-only and a
# reasonable stand-in for intraday structure, not a substitute for true futures data.
# The bias here is context, NOT an out-of-sample-validated signal like the daily tab.
# ─────────────────────────────────────────────────────────────────────────────
FUTURES = [("ES", "S&P 500 e-mini", "SPY"), ("NQ", "Nasdaq 100 e-mini", "QQQ"),
           ("RTY", "Russell 2000 e-mini", "IWM"), ("YM", "Dow e-mini", "DIA")]


def _us_dst(d):
    mar = dt.date(d.year, 3, 1)
    start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7 + 7)   # 2nd Sun of March
    nov = dt.date(d.year, 11, 1)
    end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)         # 1st Sun of Nov
    return start <= d < end


def _et(ms):
    """Epoch ms -> naive US-Eastern datetime (DST-aware, no tzdata dependency)."""
    u = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    return (u + dt.timedelta(hours=(-4 if _us_dst(u.date()) else -5))).replace(tzinfo=None)


def fetch_intraday(proxy, mult=15, days=20):
    if FORCE_SYNTH or not API_KEYS.get("polygon"):
        return synth_intraday(proxy, days)
    to = dt.date.today()
    frm = to - dt.timedelta(days=days)
    url = ("https://api.polygon.io/v2/aggs/ticker/%s/range/%d/minute/%s/%s?adjusted=true&sort=asc&limit=50000&apiKey=%s"
           % (urllib.parse.quote(proxy), mult, frm.isoformat(), to.isoformat(), urllib.parse.quote(API_KEYS["polygon"])))
    try:
        res = http_get_json(url).get("results") or []
        if res:
            return [{"t": r["t"], "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r.get("v", 0)} for r in res]
    except Exception:
        pass
    return synth_intraday(proxy, days)


def synth_intraday(proxy, days=20):
    rnd = random.Random(hash(proxy) & 0xffffff)
    price = SEED_PRICES.get(proxy, 400)
    bars = []
    today = dt.datetime.now(dt.timezone.utc)
    for back in range(days, 0, -1):
        day = (today - dt.timedelta(days=back)).date()
        if day.weekday() >= 5:
            continue
        for slot in range(26):  # ~6.5h RTH in 15-min slots, anchored mid-session in UTC
            ts = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=14 * 60 + 30 + slot * 15)
            ret = (rnd.random() - 0.5) * 0.004
            o = price; c = max(1.0, price * (1 + ret))
            h = max(o, c) * (1 + rnd.random() * 0.0012); l = min(o, c) * (1 - rnd.random() * 0.0012)
            bars.append({"t": int(ts.timestamp() * 1000), "o": round(o, 2), "h": round(h, 2),
                         "l": round(l, 2), "c": round(c, 2), "v": rnd.randint(1000, 9000)})
            price = c
    return bars


def get_intraday(proxy):
    c = cache_get("intra:" + proxy, 300)
    if c is not None:
        return c
    b = fetch_intraday(proxy)
    cache_set("intra:" + proxy, b)
    return b


def _rth_sessions(bars):
    """Group bars into RTH (09:30–16:00 ET) sessions, ordered oldest→newest."""
    sess = {}
    order = []
    for b in bars:
        et = _et(b["t"])
        mins = et.hour * 60 + et.minute
        if mins < 9 * 60 + 30 or mins >= 16 * 60:
            continue
        key = et.date()
        if key not in sess:
            sess[key] = []
            order.append(key)
        sess[key].append(b)
    return [(k, sess[k]) for k in order]


def _session_levels(sb):
    cum_pv = cum_v = 0.0
    for b in sb:
        tp = (b["h"] + b["l"] + b["c"]) / 3
        cum_pv += tp * b["v"]; cum_v += b["v"]
    vwap = cum_pv / cum_v if cum_v else sb[-1]["c"]
    orb = sb[:2] if len(sb) >= 2 else sb           # first 30 min = opening range
    return vwap, max(b["h"] for b in orb), min(b["l"] for b in orb)


def futures_state(fut):
    sym, name, proxy = fut
    bars = get_intraday(proxy)
    sess = _rth_sessions(bars)
    if not sess:
        return {"symbol": sym, "name": name, "proxy": proxy, "warming": True}
    _date, sb = sess[-1]
    closes_all = [b["c"] for b in bars]
    closes = [b["c"] for b in sb]
    vwap, orh, orl = _session_levels(sb)
    prior = sess[-2][1] if len(sess) >= 2 else None
    e9 = ema_series(closes_all, 9)[-1]
    e20 = ema_series(closes_all, 20)[-1]
    r2 = rsi(closes_all, 2)
    price = closes[-1]
    above_vwap = price > vwap
    if price > orh and above_vwap:
        bias, rank = "Long — ORB up · >VWAP", 0
    elif price < orl and not above_vwap:
        bias, rank = "Short — ORB dn · <VWAP", 0
    elif above_vwap:
        bias, rank = "Bullish (>VWAP, inside)", 1
    else:
        bias, rank = "Bearish (<VWAP, inside)", 1
    return {
        "symbol": sym, "name": name, "proxy": proxy, "price": round(price, 2),
        "vwap": round(vwap, 2), "aboveVwap": above_vwap, "vwapDist": round((price / vwap - 1) * 100, 2),
        "orh": round(orh, 2), "orl": round(orl, 2),
        "orbStatus": "above" if price > orh else "below" if price < orl else "inside",
        "priorHigh": round(max(b["h"] for b in prior), 2) if prior else None,
        "priorLow": round(min(b["l"] for b in prior), 2) if prior else None,
        "priorClose": round(prior[-1]["c"], 2) if prior else None,
        "ema9": round(e9, 2) if e9 else None, "ema20": round(e20, 2) if e20 else None,
        "emaTrend": "up" if (e9 and e20 and e9 > e20) else "down",
        "rsi2": round(r2, 1) if r2 is not None else None, "bias": bias, "rank": rank,
        "source": "polygon" if (API_KEYS.get("polygon") and not FORCE_SYNTH) else "synth",
    }


def futures_summary():
    return {"instruments": [futures_state(f) for f in FUTURES]}


def futures_chart(sym, nsess=2):
    fut = next((f for f in FUTURES if f[0] == sym.upper()), FUTURES[0])
    proxy = fut[2]
    bars = get_intraday(proxy)
    sess = _rth_sessions(bars)
    if not sess:
        return {"symbol": sym, "ok": False, "reason": "warming"}
    show_sess = sess[-nsess:]
    flat, vwap_series, new_session = [], [], []
    for si, (_d, sb) in enumerate(show_sess):
        cum_pv = cum_v = 0.0
        for j, b in enumerate(sb):
            tp = (b["h"] + b["l"] + b["c"]) / 3
            cum_pv += tp * b["v"]; cum_v += b["v"]
            vwap_series.append(round(cum_pv / cum_v, 2) if cum_v else b["c"])
            if j == 0 and si > 0:
                new_session.append(len(flat))
            flat.append(b)
    st = futures_state(fut)
    closes = [b["c"] for b in flat]
    e9 = ema_series([b["c"] for b in bars], 9)
    e20 = ema_series([b["c"] for b in bars], 20)
    tail = len(flat)
    return {"symbol": sym, "proxy": proxy, "ok": True, "bars": flat, "vwap": vwap_series,
            "newSession": new_session, "ema9": e9[-tail:], "ema20": e20[-tail:],
            "orh": st.get("orh"), "orl": st.get("orl"),
            "priorHigh": st.get("priorHigh"), "priorLow": st.get("priorLow"), "state": st}


# ─────────────────────────────────────────────────────────────────────────────
# News (Finnhub) + classification
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_RULES = [
    ("Fed", ["fed", "fomc", "powell", "rate cut", "rate hike", "interest rate", "central bank"]),
    ("Inflation", ["cpi", "ppi", "inflation", "pce", "deflation"]),
    ("Jobs", ["jobs", "payroll", "nfp", "unemployment", "jobless", "labor market"]),
    ("Earnings", ["earnings", "eps", "revenue", "guidance", "beats", "misses", "quarter"]),
    ("M&A", ["acquire", "acquisition", "merger", "buyout", "takeover"]),
    ("Upgrade", ["upgrade", "raised to", "outperform", "overweight", "price target raised"]),
    ("Downgrade", ["downgrade", "cut to", "underperform", "underweight", "price target cut"]),
    ("Geopolitics", ["war", "sanction", "tariff", "opec", "conflict", "election", "geopolit"]),
    ("Crypto", ["bitcoin", "ethereum", "crypto", "btc"]),
    ("Legal", ["lawsuit", "sec charges", "fraud", "settlement", "antitrust", "investigation"]),
]
BULL_WORDS = ["beats", "surge", "soar", "jumps", "rally", "record", "upgrade", "raises", "tops", "strong", "growth", "approval", "wins", "gains", "outperform", "bullish"]
BEAR_WORDS = ["misses", "plunge", "slump", "falls", "drops", "downgrade", "cuts", "warns", "weak", "lawsuit", "bankruptcy", "recall", "probe", "layoffs", "loss", "bearish", "halts"]


def classify(text):
    t = (text or "").lower()
    category = "General"
    for name, words in CATEGORY_RULES:
        if any(w in t for w in words):
            category = name; break
    score = sum(w in t for w in BULL_WORDS) - sum(w in t for w in BEAR_WORDS)
    sentiment = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    impact = 85 if category in ("Fed", "Inflation", "Jobs") else 65 if category in ("Earnings", "M&A", "Geopolitics") else 40
    return category, sentiment, min(100, impact + 8 * abs(score))


def fetch_news():
    if not API_KEYS.get("finnhub"):
        return {"error": "Finnhub key required for live news", "items": []}
    try:
        raw = http_get_json("%s/news?category=general&token=%s" % (FINNHUB, urllib.parse.quote(API_KEYS["finnhub"])))
    except Exception as e:
        return {"error": "news fetch failed: %s" % e, "items": []}
    items = []
    for n in raw[:60]:
        head = n.get("headline", "")
        cat, sent, impact = classify(head + " " + n.get("summary", ""))
        items.append({"headline": head, "source": n.get("source", ""), "url": n.get("url", ""),
                      "summary": (n.get("summary", "") or "")[:280], "datetime": n.get("datetime", 0),
                      "related": n.get("related", ""), "category": cat, "sentiment": sent, "impact": impact})
    items.sort(key=lambda x: x["datetime"], reverse=True)  # chronological, newest first
    return {"items": items}


def news_loop():
    while True:
        d = fetch_news()
        if not d.get("error") or not cache_get("news", 1e9):
            cache_set("news", d)
        time.sleep(180)


# ─────────────────────────────────────────────────────────────────────────────
# Economic calendar (free FairEconomy/ForexFactory feed) + Finnhub earnings
# ─────────────────────────────────────────────────────────────────────────────
FAIRECONOMY_FEEDS = ["https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                     "https://nfs.faireconomy.media/ff_calendar_nextweek.json"]
# Broad default so the UI can filter currencies; set CALENDAR_COUNTRIES="" for all.
CALENDAR_COUNTRIES = set(c.strip().upper() for c in os.environ.get(
    "CALENDAR_COUNTRIES", "USD,EUR,GBP,JPY,CAD,AUD,CHF,NZD,CNY").split(",") if c.strip())


def _parse_num(s):
    if s is None:
        return None
    t = str(s).strip().replace(",", "")
    if t in ("", "-"):
        return None
    mult = 1.0
    if t and t[-1] in "KkMmBbTt":
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}[t[-1].lower()]; t = t[:-1]
    neg = t.startswith("-")
    num = "".join(ch for ch in t if ch.isdigit() or ch == ".")
    if num in ("", "."):
        return None
    try:
        v = float(num) * mult
        return -v if neg else v
    except ValueError:
        return None


def fetch_economic():
    events = []
    for url in FAIRECONOMY_FEEDS:
        try:
            data = http_get_json(url)
        except Exception:
            continue
        for e in data:
            country = (e.get("country") or "").upper()
            if CALENDAR_COUNTRIES and country not in CALENDAR_COUNTRIES:
                continue
            ts = e.get("date", "") or ""
            f, a = _parse_num(e.get("forecast", "")), _parse_num(e.get("actual", ""))
            surprise = round((a - f) / abs(f) * 100, 1) if (f is not None and a is not None and f != 0) else None
            events.append({"date": ts[:10], "time": ts, "country": country, "event": e.get("title", ""),
                           "impact": e.get("impact", ""), "estimate": e.get("forecast", ""),
                           "prev": e.get("previous", ""), "actual": e.get("actual", ""), "surprise": surprise})
    events.sort(key=lambda x: x["time"])
    return events


def fetch_calendar():
    out = {"earnings": [], "economic": [], "notes": []}
    try:
        out["economic"] = fetch_economic()
        if not out["economic"]:
            out["notes"].append("No economic events for the current window.")
    except Exception as e:
        out["notes"].append("Economic feed unavailable (%s)." % e)
    if API_KEYS.get("finnhub"):
        today = dt.date.today()
        frm, to = today.isoformat(), (today + dt.timedelta(days=7)).isoformat()
        try:
            url = "%s/calendar/earnings?from=%s&to=%s&token=%s" % (FINNHUB, frm, to, urllib.parse.quote(API_KEYS["finnhub"]))
            for e in (http_get_json(url).get("earningsCalendar", []) or [])[:100]:
                out["earnings"].append({"date": e.get("date"), "symbol": e.get("symbol"), "hour": e.get("hour", ""),
                                        "epsEstimate": e.get("epsEstimate"), "epsActual": e.get("epsActual")})
        except Exception as e:
            out["notes"].append("Earnings calendar unavailable (%s)." % e)
    else:
        out["notes"].append("Set a Finnhub key to see the earnings calendar.")
    return out


def calendar_loop():
    while True:
        try:
            cache_set("calendar", fetch_calendar())
        except Exception:
            pass
        time.sleep(1800)


# ─────────────────────────────────────────────────────────────────────────────
# Persistent state — open positions + custom price alerts (survives restarts).
# Lives in QUANTA_DATA (mount a volume in Docker) or next to quanta.py.
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("QUANTA_DATA", "") or os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(DATA_DIR, "quanta_state.json")
_state_lock = threading.Lock()
_state = {"positions": [], "closed": [], "price_alerts": [], "next_id": 1}


def load_state():
    try:
        with open(STATE_PATH) as f:
            d = json.load(f)
        with _state_lock:
            for k in _state:
                if k in d:
                    _state[k] = d[k]
    except (FileNotFoundError, ValueError):
        pass


def save_state():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with _state_lock:
            body = json.dumps(_state, indent=1)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            f.write(body)
        os.replace(tmp, STATE_PATH)
    except OSError as e:
        print("warn: could not persist state (%s) — positions/alerts won't survive restart" % e)


def _next_id():
    with _state_lock:
        i = _state["next_id"]
        _state["next_id"] = i + 1
    return i


# ─────────────────────────────────────────────────────────────────────────────
# Live quotes for the alert/chart universe (sector ETFs + index ETFs + anything
# you hold or have a price alert on). Separate from the Markets-tab loop so the
# free-tier rate limits stay comfortable.
# ─────────────────────────────────────────────────────────────────────────────
_live_lock, _live = threading.Lock(), {}    # sym -> {last, change, changePercent, ts, source}


def live_universe():
    syms = [s for s, _ in SECTORS] + [BENCH, "QQQ", "IWM"]
    with _state_lock:
        syms += [p["symbol"] for p in _state["positions"]]
        syms += [a["symbol"] for a in _state["price_alerts"] if not a.get("fired")]
    out = []
    for s in syms:
        if s not in out:
            out.append(s)
    return out


def get_live(sym, max_age=120):
    with _live_lock:
        d = _live.get(sym)
    return d if d and (time.time() - d["ts"]) <= max_age else None


def _seed_mock_from_bars(sym):
    """In demo mode, start the mock random-walk at the synthetic bars' last close so
    live prices, charts and alerts stay coherent with each other."""
    if sym in _mock_q:
        return
    b = get_bars(sym)
    if b:
        base = b[-1]["c"]
        _mock_q[sym] = {"last": base, "pc": b[-2]["c"] if len(b) > 1 else base,
                        "o": base, "h": base, "l": base, "v": 10_000_000}


def live_loop():
    provider = active_provider()
    fn = QUOTE_FNS[provider]
    while True:
        for sym in live_universe():
            try:
                if provider == "mock":
                    _seed_mock_from_bars(sym)
                q = fn(sym, sym)
                src = provider
            except Exception:
                _seed_mock_from_bars(sym)
                q = quote_mock(sym, sym)
                src = "mock"
            with _live_lock:
                _live[sym] = {"last": q["last"], "change": q.get("change"),
                              "changePercent": q.get("changePercent"),
                              "ts": time.time(), "source": src}
            if provider == "alphavantage":
                time.sleep(13)
        check_alerts()
        time.sleep(30)


def _live_px(sym):
    d = get_live(sym, max_age=300)
    if d and d.get("last"):
        return d["last"]
    b = get_bars(sym)
    return b[-1]["c"] if b else None


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio — open positions with live P&L, R-multiples and progress-to-target.
# ─────────────────────────────────────────────────────────────────────────────
def _fnum(v):
    if v in (None, ""):
        return None
    return float(v)


def position_add(d):
    sym = str(d.get("symbol", "")).upper().strip()
    entry = _fnum(d.get("entry"))
    if not sym or entry is None or entry <= 0:
        return {"ok": False, "error": "symbol and entry price are required"}
    p = {"id": _next_id(), "symbol": sym,
         "dir": "short" if d.get("dir") == "short" else "long",
         "qty": _fnum(d.get("qty")) or 1,
         "entry": entry, "stop": _fnum(d.get("stop")), "target": _fnum(d.get("target")),
         "note": str(d.get("note", ""))[:120], "opened": time.time()}
    with _state_lock:
        _state["positions"].append(p)
    save_state()
    push_alert("position", sym, "position opened: %s %g @ %.2f (stop %s · target %s)"
               % (p["dir"], p["qty"], p["entry"],
                  ("%.2f" % p["stop"]) if p["stop"] else "—",
                  ("%.2f" % p["target"]) if p["target"] else "—"), "info", entry, dedupe_hours=0)
    return {"ok": True, "position": p}


def position_close(d):
    pid = int(d.get("id", 0))
    with _state_lock:
        p = next((x for x in _state["positions"] if x["id"] == pid), None)
    if not p:
        return {"ok": False, "error": "position not found"}
    exit_px = _fnum(d.get("price")) or _live_px(p["symbol"]) or p["entry"]
    sgn = 1 if p["dir"] == "long" else -1
    pl = (exit_px - p["entry"]) * sgn * (p.get("qty") or 1)
    with _state_lock:
        _state["positions"] = [x for x in _state["positions"] if x["id"] != pid]
        _state["closed"].append({**p, "exit": round(exit_px, 4), "pl": round(pl, 2), "closedAt": time.time()})
        del _state["closed"][:-200]
    save_state()
    return {"ok": True, "pl": round(pl, 2), "exit": round(exit_px, 2)}


def position_delete(d):
    pid = int(d.get("id", 0))
    with _state_lock:
        n0 = len(_state["positions"])
        _state["positions"] = [x for x in _state["positions"] if x["id"] != pid]
        changed = len(_state["positions"]) != n0
    if changed:
        save_state()
    return {"ok": changed}


def positions_view():
    with _state_lock:
        open_p = [dict(p) for p in _state["positions"]]
        closed = [dict(p) for p in _state["closed"][-50:]]
    rows, tot_val, tot_pl, alloc = [], 0.0, 0.0, {}
    for p in open_p:
        px = _live_px(p["symbol"])
        sgn = 1 if p["dir"] == "long" else -1
        qty = p.get("qty") or 1
        pl = plpct = rmult = prog = None
        if px:
            pl = (px - p["entry"]) * sgn * qty
            plpct = (px / p["entry"] - 1) * 100 * sgn
            risk = abs(p["entry"] - p["stop"]) if p.get("stop") else None
            if risk:
                rmult = (px - p["entry"]) * sgn / risk
            if p.get("target") and p["target"] != p["entry"]:
                prog = (px - p["entry"]) / (p["target"] - p["entry"]) * 100
            val = px * qty
            tot_val += val
            tot_pl += pl
            alloc[p["symbol"]] = alloc.get(p["symbol"], 0) + val
        live = get_live(p["symbol"], 300)
        rows.append({**p, "last": round(px, 2) if px else None,
                     "liveSource": live.get("source") if live else "bars",
                     "pl": round(pl, 2) if pl is not None else None,
                     "plPct": round(plpct, 2) if plpct is not None else None,
                     "rMult": round(rmult, 2) if rmult is not None else None,
                     "progress": round(prog, 1) if prog is not None else None,
                     "distStop": round((px / p["stop"] - 1) * 100, 2) if (px and p.get("stop")) else None,
                     "distTarget": round((px / p["target"] - 1) * 100, 2) if (px and p.get("target")) else None})
    by_sym = {}
    for c in closed:
        by_sym.setdefault(c["symbol"], 0.0)
        by_sym[c["symbol"]] += c.get("pl") or 0
    return {"open": rows, "closed": closed[::-1],
            "totalValue": round(tot_val, 2), "openPL": round(tot_pl, 2),
            "realizedPL": round(sum(by_sym.values()), 2),
            "realizedBySymbol": [{"symbol": k, "pl": round(v, 2)} for k, v in
                                 sorted(by_sym.items(), key=lambda kv: -kv[1])],
            "alloc": [{"symbol": k, "value": round(v, 2),
                       "pct": round(v / tot_val * 100, 1) if tot_val else 0}
                      for k, v in sorted(alloc.items(), key=lambda kv: -kv[1])]}


def price_alert_add(d):
    sym = str(d.get("symbol", "")).upper().strip()
    px = _fnum(d.get("price"))
    op = ">=" if d.get("op") != "<=" else "<="
    if not sym or px is None or px <= 0:
        return {"ok": False, "error": "symbol and price are required"}
    a = {"id": _next_id(), "symbol": sym, "op": op, "price": px,
         "note": str(d.get("note", ""))[:120], "fired": False, "created": time.time()}
    with _state_lock:
        _state["price_alerts"].append(a)
    save_state()
    return {"ok": True, "alert": a}


def price_alert_delete(d):
    aid = int(d.get("id", 0))
    with _state_lock:
        n0 = len(_state["price_alerts"])
        _state["price_alerts"] = [x for x in _state["price_alerts"] if x["id"] != aid]
        changed = len(_state["price_alerts"]) != n0
    if changed:
        save_state()
    return {"ok": changed}


# ─────────────────────────────────────────────────────────────────────────────
# Alert engine — evaluated after every live-quote sweep (~30s). Alerts fire for:
#   * RSI(2) signal changes (BUY triggered / arming / exit trigger)
#   * 50%-retracement setups going Ready, or price approaching the entry zone
#   * open positions approaching (or hitting) their stop / target
#   * custom price alerts
# Everything is deduped so the feed doesn't spam the same message all day.
# ─────────────────────────────────────────────────────────────────────────────
_alerts_lock = threading.Lock()
_alerts = []              # newest first, capped
_alert_seen = {}          # dedupe key -> last fired ts
_alert_seq = [0]
_ALERTS_MAX = 200


def push_alert(kind, symbol, msg, level="info", price=None, dedupe_hours=12.0, key=None):
    # Dedupe on `key` when the message embeds a moving price (else on the message).
    key = "%s|%s|%s" % (kind, symbol, key or msg)
    now = time.time()
    with _alerts_lock:
        if dedupe_hours and now - _alert_seen.get(key, 0) < dedupe_hours * 3600:
            return False
        _alert_seen[key] = now
        _alert_seq[0] += 1
        _alerts.insert(0, {"id": _alert_seq[0], "ts": now, "kind": kind, "symbol": symbol,
                           "msg": msg, "level": level,
                           "price": round(price, 2) if price else None})
        del _alerts[_ALERTS_MAX:]
    return True


_prev_signal = {}


def _check_signal_alerts():
    d = signals()
    for s in d.get("sectors", []):
        if s.get("warming"):
            continue
        sym, sig = s["symbol"], s["signal"]
        prev = _prev_signal.get(sym)
        if prev is not None and sig != prev:
            if sig == "BUY":
                push_alert("signal", sym, "RSI(2) BUY triggered — RSI2 %.1f; enter near the close, exit close > 5-SMA"
                           % (s.get("rsi2") or 0), "buy", s.get("priceLive") or s.get("price"))
            elif sig == "Arming":
                push_alert("signal", sym, "RSI(2) arming — RSI2 %.1f and under the 5-SMA; a BUY may set up"
                           % (s.get("rsi2") or 0), "info", s.get("priceLive") or s.get("price"))
            elif prev == "BUY" and (s.get("distExit") or 0) > 0:
                push_alert("signal", sym, "RSI(2) exit trigger — close back above the 5-day SMA; take the bounce",
                           "sell", s.get("priceLive") or s.get("price"))
        _prev_signal[sym] = sig


def _check_setup_alerts():
    for sym, _name in SECTORS:
        a = analyze(sym)
        if not a.get("ok"):
            continue
        px = _live_px(sym) or a["price"]
        av = a.get("atr") or 0
        if a["status"] == "Ready":
            push_alert("setup", sym, "50%% pullback READY (%s, score %s) — entry %.2f · stop %.2f · target %.2f"
                       % (a["direction"], a["score"], a["entry"], a["stop"], a["target"]),
                       "setup", px, dedupe_hours=24, key="ready-" + a["direction"])
        elif a["status"] == "Approaching" and av and abs(px - a["entry"]) <= 0.75 * av:
            push_alert("setup", sym, "approaching the 50%% entry %.2f (now %.2f, %+.1f%% away · %s)"
                       % (a["entry"], px, (px / a["entry"] - 1) * 100, a["direction"]),
                       "info", px, dedupe_hours=24, key="near-entry-" + a["direction"])


def _check_position_alerts():
    with _state_lock:
        positions = [dict(p) for p in _state["positions"]]
    for p in positions:
        px = _live_px(p["symbol"])
        if not px:
            continue
        sgn = 1 if p["dir"] == "long" else -1
        ent, stp, tgt = p["entry"], p.get("stop"), p.get("target")
        if tgt:
            if (px - tgt) * sgn >= 0:
                push_alert("position", p["symbol"], "TARGET HIT — now %.2f vs target %.2f; consider taking profit"
                           % (px, tgt), "target", px, dedupe_hours=24, key="target-hit-%d" % p["id"])
            else:
                total = abs(tgt - ent)
                done = (px - ent) * sgn
                if total and done / total >= 0.85:
                    push_alert("position", p["symbol"], "approaching target %.2f — %.0f%% of the move done (now %.2f)"
                               % (tgt, done / total * 100, px), "warn", px, key="near-target-%d" % p["id"])
        if stp:
            if (stp - px) * sgn >= 0:
                push_alert("position", p["symbol"], "STOP HIT — now %.2f vs stop %.2f; exit per plan"
                           % (px, stp), "stop", px, dedupe_hours=24, key="stop-hit-%d" % p["id"])
            else:
                risk = abs(ent - stp)
                adverse = (ent - px) * sgn
                if risk and adverse / risk >= 0.75:
                    push_alert("position", p["symbol"], "approaching stop %.2f — %.0f%% of planned risk used (now %.2f)"
                               % (stp, adverse / risk * 100, px), "warn", px, key="near-stop-%d" % p["id"])


_prev_model = []


def _check_rotation_alerts():
    global _prev_model
    m = rotation().get("model")
    if not m:
        return
    hold = m["holdings"]
    if _prev_model and set(hold) != set(_prev_model):
        added = [s for s in hold if s not in _prev_model]
        dropped = [s for s in _prev_model if s not in hold]
        push_alert("rotation", ", ".join(added) or "SECTORS",
                   "rotation model change — in: %s · out: %s (top-3 by 1-month RS vs SPY)"
                   % (", ".join(added) or "—", ", ".join(dropped) or "—"), "setup", dedupe_hours=12)
    _prev_model = hold


def _check_price_alerts():
    fired = False
    with _state_lock:
        pending = [dict(a) for a in _state["price_alerts"] if not a.get("fired")]
    for a in pending:
        px = _live_px(a["symbol"])
        if not px:
            continue
        hit = px >= a["price"] if a["op"] == ">=" else px <= a["price"]
        if hit:
            push_alert("price", a["symbol"], "price alert hit: %s %s %.2f (now %.2f)%s"
                       % (a["symbol"], a["op"], a["price"], px,
                          (" — " + a["note"]) if a.get("note") else ""), "price", px, dedupe_hours=0)
            with _state_lock:
                a2 = next((x for x in _state["price_alerts"] if x["id"] == a["id"]), None)
                if a2:
                    a2["fired"] = True
                    a2["firedAt"] = time.time()
                    a2["firedPx"] = round(px, 2)
            fired = True
    if fired:
        save_state()


def check_alerts():
    for fn in (_check_signal_alerts, _check_setup_alerts, _check_rotation_alerts,
               _check_position_alerts, _check_price_alerts):
        try:
            fn()
        except Exception as e:
            print("warn: alert check %s failed: %s" % (fn.__name__, e))


# ─────────────────────────────────────────────────────────────────────────────
# HTTP server
# ─────────────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path, qs = u.path, urllib.parse.parse_qs(u.query)
        tf = "weekly" if (qs.get("tf", ["daily"])[0] == "weekly") else "daily"

        if path == "/api/quotes":
            with _quotes_lock:
                self._json({"provider": _status["provider"], "updated": _status["updated"], "quotes": list(_quotes_cache)})
        elif path == "/api/sectors":
            self._json(cache_get("sectors", 120) or _cache_and_return("sectors", rotation))
        elif path == "/api/signals":
            self._json(cache_get("signals", 120) or _cache_and_return("signals", signals))
        elif path == "/api/entries":
            syms = [s.strip().upper() for s in (qs.get("symbols", [""])[0]).split(",") if s.strip()] \
                   or [s for s, _ in SECTORS]   # sector ETFs only by default
            ck = "entries:%s:%s" % (tf, ",".join(syms))
            self._json(cache_get(ck, 120) or _cache_and_return(ck, lambda: build_entries(syms, tf)))
        elif path == "/api/chart":
            sym = (qs.get("symbol", ["SPY"])[0]).upper()
            self._json(chart_data(sym, tf))
        elif path == "/api/futures":
            self._json(cache_get("futures", 60) or _cache_and_return("futures", futures_summary))
        elif path == "/api/futures_chart":
            self._json(futures_chart((qs.get("symbol", ["ES"])[0]).upper()))
        elif path == "/api/news":
            self._json(cache_get("news", 1e9) or fetch_news())
        elif path == "/api/calendar":
            self._json(cache_get("calendar", 1e9) or fetch_calendar())
        elif path == "/api/live":
            with _live_lock:
                self._json({"quotes": {k: dict(v) for k, v in _live.items()}, "serverTime": time.time()})
        elif path == "/api/alerts":
            with _alerts_lock:
                items = [dict(a) for a in _alerts]
            with _state_lock:
                pending = [dict(a) for a in _state["price_alerts"]]
            self._json({"alerts": items, "priceAlerts": pending, "serverTime": time.time()})
        elif path == "/api/portfolio":
            self._json(positions_view())
        elif path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"index.html not found next to quanta.py", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    POST_ROUTES = {
        "/api/portfolio/add": position_add,
        "/api/portfolio/close": position_close,
        "/api/portfolio/delete": position_delete,
        "/api/alert/add": price_alert_add,
        "/api/alert/delete": price_alert_delete,
    }

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        fn = self.POST_ROUTES.get(path)
        if not fn:
            self._send(404, b"not found", "text/plain")
            return
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            d = json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}
            if not isinstance(d, dict):
                raise ValueError("expected a JSON object")
        except (ValueError, UnicodeDecodeError) as e:
            self._json({"ok": False, "error": "bad request: %s" % e}, 400)
            return
        try:
            self._json(fn(d))
        except (KeyError, TypeError, ValueError) as e:
            self._json({"ok": False, "error": str(e)}, 400)

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def log_message(self, *args):
        pass


def _cache_and_return(key, fn):
    val = fn(); cache_set(key, val); return val


def main():
    prov = active_provider()
    bars_src = "synthetic (demo)" if (FORCE_SYNTH or not API_KEYS.get("polygon")) else "polygon (daily aggregates)"
    load_state()
    with _state_lock:
        n_pos, n_pa = len(_state["positions"]), len([a for a in _state["price_alerts"] if not a.get("fired")])
    print("Quanta — quant swing companion")
    print("  quotes   : %s%s" % (prov, "  (no API key)" if prov == "mock" else ""))
    print("  bars     : %s — warming %d symbols in the background" % (bars_src, len(BAR_UNIVERSE)))
    print("  sectors  : %s" % ", ".join(s for s, _ in SECTORS))
    print("  state    : %s (%d open positions, %d price alerts)" % (STATE_PATH, n_pos, n_pa))
    print("  alerts   : signals · setups · position stop/target · price levels (checked ~30s)")
    print("  open     : http://localhost:%d/" % PORT)
    for fn in (quotes_loop, bars_loop, live_loop, news_loop, calendar_loop):
        threading.Thread(target=fn, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down"); server.shutdown()


if __name__ == "__main__":
    main()
