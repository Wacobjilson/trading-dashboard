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
import socket
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

# Macro/context proxies (all liquid ETFs, so free-tier bars work). Used for the
# correlation columns, the macro-tailwind score category, and equal-weight RS.
# RSP = equal-weight S&P (breadth), TLT = long Treasuries (rates, inverted),
# UUP = dollar, USO = crude, GLD = gold, CPER = copper, VIXY = VIX-futures proxy.
MACRO_PROXIES = [
    ("RSP", "Equal-weight S&P 500"), ("TLT", "20y+ Treasuries (rates ↓)"),
    ("UUP", "US Dollar"), ("USO", "Crude Oil"), ("GLD", "Gold"),
    ("CPER", "Copper"), ("VIXY", "VIX futures (proxy)"),
    ("HYG", "High-yield credit (risk appetite)"),
]

# Everything we keep historical bars for (sectors first so the UI warms fastest).
BAR_UNIVERSE = []
for _s in [BENCH, "QQQ", "IWM"] + [s for s, _ in SECTORS] + WATCHLIST + [s for s, _ in MACRO_PROXIES]:
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


def adx(bars, n=14):
    """Wilder ADX — trend quality (>25 trending, <20 chop)."""
    if len(bars) < 2 * n + 2:
        return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(bars)):
        up = bars[i]["h"] - bars[i - 1]["h"]
        dn = bars[i - 1]["l"] - bars[i]["l"]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i - 1]["c"]),
                       abs(bars[i]["l"] - bars[i - 1]["c"])))
    atr_s, pdm, mdm = sum(trs[:n]), sum(plus_dm[:n]), sum(minus_dm[:n])
    dxs = []
    for i in range(n, len(trs)):
        atr_s = atr_s - atr_s / n + trs[i]
        pdm = pdm - pdm / n + plus_dm[i]
        mdm = mdm - mdm / n + minus_dm[i]
        pdi = 100 * pdm / atr_s if atr_s else 0.0
        mdi = 100 * mdm / atr_s if atr_s else 0.0
        dxs.append(100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0)
    if len(dxs) < n:
        return None
    a = sum(dxs[:n]) / n
    for d in dxs[n:]:
        a = (a * (n - 1) + d) / n
    return a


def correlation(c1, c2, n=63):
    """Pearson correlation of daily returns over the last n days."""
    m = min(len(c1), len(c2), n + 1)
    if m < 21:
        return None
    r1 = [c1[-i] / c1[-i - 1] - 1 for i in range(1, m) if c1[-i - 1]]
    r2 = [c2[-i] / c2[-i - 1] - 1 for i in range(1, m) if c2[-i - 1]]
    m = min(len(r1), len(r2))
    r1, r2 = r1[:m], r2[:m]
    mu1, mu2 = sum(r1) / m, sum(r2) / m
    cov = sum((a - mu1) * (b - mu2) for a, b in zip(r1, r2)) / m
    s1 = (sum((a - mu1) ** 2 for a in r1) / m) ** 0.5
    s2 = (sum((b - mu2) ** 2 for b in r2) / m) ** 0.5
    return cov / (s1 * s2) if s1 > 0 and s2 > 0 else None


def updown_volume(bars, n=20):
    """Up-day volume / down-day volume over n days — crude accumulation gauge."""
    seg = bars[-n:]
    upv = sum(b.get("v", 0) for b in seg if b["c"] >= b["o"])
    dnv = sum(b.get("v", 0) for b in seg if b["c"] < b["o"])
    return (upv / dnv) if dnv > 0 else None


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

    # reference series for equal-weight RS and the correlation columns
    refs = {}
    for rsym in ("RSP", "QQQ", "TLT", "VIXY"):
        rb = get_bars(rsym)
        if rb:
            refs[rsym] = [b["c"] for b in rb]

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
        # equal-weight RS (vs RSP), trend quality (ADX), correlations, options read
        rs_ew = None
        if "RSP" in refs:
            a, b2 = pct_return(c, 63), pct_return(refs["RSP"], 63)
            rs_ew = round(a - b2, 2) if (a is not None and b2 is not None) else None
        ax = adx(bars, 14)
        corrs = {r: correlation(c, refs[r], 63) for r in refs}
        cspy = correlation(c, spc, 63)
        opt = get_options(sym) or {}
        out["sectors"].append({
            "symbol": sym, "name": name, "price": round(c[-1], 2),
            "chg1d": round(pct_return(c, 1) or 0, 2), "rs1w": r1w, "rs1m": r1m, "rs3m": r3m,
            "rs6m": r6m, "rs1y": r1y, "rsEW3m": rs_ew,
            "rsRatio": round(ratio, 2), "rsMom": round(mom, 2), "quadrant": quad,
            "trend": "up" if (s50 and c[-1] > s50) else "down",
            "above20": bool(s20 and c[-1] > s20), "above50": bool(s50 and c[-1] > s50),
            "above200": bool(s200 and c[-1] > s200), "volAdj": vol_adj, "relVol": rel_vol,
            "adx": round(ax, 1) if ax is not None else None,
            "corrSPY": round(cspy, 2) if cspy is not None else None,
            "corrQQQ": round(corrs["QQQ"], 2) if corrs.get("QQQ") is not None else None,
            "corrTLT": round(corrs["TLT"], 2) if corrs.get("TLT") is not None else None,
            "corrVIX": round(corrs["VIXY"], 2) if corrs.get("VIXY") is not None else None,
            "pcrOI": opt.get("pcrOI"), "netGEX": opt.get("netGEX"),
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


# ─────────────────────────────────────────────────────────────────────────────
# Market Intelligence Engine — one explainable 0-100 score per sector, blending
# eight independent evidence categories. Weights are configurable (env
# QUANTA_SCORE_WEIGHTS as JSON, or ?weights=trend:0.2,rs:0.3 on /api/scores);
# categories with no data (e.g. options before the chain feed loads) are
# EXCLUDED and the rest renormalized — never silently defaulted. Every category
# returns a `detail` string with the numbers behind it, and confidence reflects
# both data coverage and cross-category agreement. News/ETF-flow categories are
# intentionally absent: no reliable per-sector source on the free tier.
# ─────────────────────────────────────────────────────────────────────────────
# Composite weights are EVIDENCE-BASED (research_categories.py, 2026-07-03 run:
# 54 weekly cross-sections on 2yr Polygon bars, Spearman IC vs forward 10d
# SPY-relative returns, train/test + ablation):
#   rs          train IC +0.031 / test +0.017 — the ONLY survivor; ablation:
#               removing it costs −0.041 composite IC → carries the weight.
#   trend       redundant with rs (ρ=0.81) and sign-flipped → weight 0 (context).
#   momentum    train IC −0.061 → weight 0 (context).
#   volume      train IC −0.161 → weight 0 (context).
#   volatility  WRONG-SIGNED as selection signal (IC21 −0.213, t=−4.8): calm
#               sectors underperformed. Weight 0; kept visible as risk info.
#               (Inverting it would be a post-hoc sign flip = curve-fit — parked
#               as a research hypothesis until more history exists.)
#   options/macro: no reconstructible history to validate yet → small
#               PROVISIONAL weights, flagged "unvalidated" in the UI; the daily
#               snapshot files will eventually allow the same IC test.
# "breadth" was removed as a per-sector category (market context ± quadrant,
# which duplicates rs) — it now lives in the regime block.
SCORE_WEIGHTS = {"rs": 0.70, "options": 0.15, "macro": 0.15}
CONTEXT_CATS = {   # displayed with 0 weight + their measured ICs, never composited
    "trend": "0 weight — failed validation (train IC −0.03, ρ 0.81 with RS = redundant)",
    "momentum": "0 weight — failed validation (train IC −0.06)",
    "volume": "0 weight — failed validation (train IC −0.16)",
    "volatility": "0 weight — WRONG-SIGNED as selection (IC21 −0.21, t −4.8); read as risk info",
}
try:
    SCORE_WEIGHTS.update({k: float(v) for k, v in
                          json.loads(os.environ.get("QUANTA_SCORE_WEIGHTS", "{}")).items()
                          if k in SCORE_WEIGHTS})
except (ValueError, AttributeError):
    pass

# How each macro proxy's 1-month trend maps onto sectors (directional context,
# blended with the *measured* 63-day correlation — the correlation carries the
# sign if the two disagree).
MACRO_INFLUENCE = {
    "TLT": {"helps": ["XLU", "XLRE", "XLP", "XLK"], "hurts": ["XLF"],
            "note": "TLT up = yields down: helps rate-sensitive Utilities/REITs/Staples and long-duration Tech; compresses bank margins (XLF)."},
    "UUP": {"helps": [], "hurts": ["XLB", "XLE", "XLI"],
            "note": "Strong dollar pressures commodities and multinational earnings (Materials, Energy, Industrials)."},
    "USO": {"helps": ["XLE"], "hurts": ["XLY", "XLI"],
            "note": "Crude up lifts Energy; taxes the consumer (XLY) and transport-heavy Industrials."},
    "GLD": {"helps": ["XLB"], "hurts": [],
            "note": "Gold up often signals falling real yields / risk hedging; mild Materials tailwind."},
    "CPER": {"helps": ["XLB", "XLI"], "hurts": [],
             "note": "Copper up = global growth impulse: Materials and Industrials lead."},
    "VIXY": {"helps": ["XLP", "XLU", "XLV"], "hurts": ["XLK", "XLY", "XLF"],
             "note": "Vol regime rising favors defensives (Staples/Utilities/Health) over high-beta cyclicals."},
    "HYG": {"helps": ["XLF", "XLY", "XLI", "XLE"], "hurts": [],
            "note": "High-yield credit strength = risk appetite / tight spreads: supports cyclicals and Financials."},
}


def _pct_rank(vals, v):
    """Percentile rank of v within vals (0..1)."""
    vs = [x for x in vals if x is not None]
    if v is None or not vs:
        return None
    return sum(1 for x in vs if x <= v) / len(vs)


def _cat(score, detail):
    return {"score": round(clamp(score), 1), "detail": detail}


def _bar_categories(bars, spy_closes, rs_rank, atr_rank):
    """The five categories derivable from bars alone (also used for history)."""
    c = [b["c"] for b in bars]
    close = c[-1]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    s20p = sma(c[:-5], 20) if len(c) > 30 else None
    ax = adx(bars, 14)
    t = 0.0
    t += 15 if (s20 and close > s20) else 0
    t += 15 if (s50 and close > s50) else 0
    t += 20 if (s200 and close > s200) else 0
    t += 10 if (s50 and s200 and s50 > s200) else 0
    t += 10 if (s20p and s20 and s20 > s20p) else 0
    t += min(30.0, ax or 0)
    trend = _cat(t, "px %s SMA20/50/200: %s%s%s · SMA50%sSMA200 · ADX %.0f"
                 % (">" if (s20 and close > s20) else "≤",
                    "✓" if (s20 and close > s20) else "✗",
                    "✓" if (s50 and close > s50) else "✗",
                    "✓" if (s200 and close > s200) else "✗",
                    ">" if (s50 and s200 and s50 > s200) else "≤", ax or 0))
    rs = _cat((rs_rank or 0.5) * 100,
              "RS blend rank %.0f%% of sectors (0.5·1m + 0.3·3m + 0.2·6m vs SPY)" % ((rs_rank or 0.5) * 100))
    r14 = rsi(c, 14)
    hist_now, hist_prev = macd_hist(c)
    roc21 = pct_return(c, 21)
    m = 50.0
    m += clamp((r14 or 50) - 50, -25, 25)
    if hist_now is not None and hist_prev is not None:
        m += 15 if hist_now > hist_prev else -15
        m += 5 if hist_now > 0 else -5
    m += clamp((roc21 or 0) * 1.5, -10, 10)
    momentum = _cat(m, "RSI14 %.0f · MACD hist %s%s · 21d ROC %+.1f%%"
                    % (r14 or 0, "rising" if (hist_now or 0) > (hist_prev or 0) else "falling",
                       " >0" if (hist_now or 0) > 0 else " <0", roc21 or 0))
    ud = updown_volume(bars, 20)
    v = 50.0 if ud is None else clamp(50 + (ud - 1) * 40)
    volume = _cat(v, "up/down volume 20d = %s (accumulation >1)" % ("n/a" if ud is None else "%.2f" % ud))
    av = atr(bars, 14)
    atrp = (av / close * 100) if (av and close) else None
    rets = [c[i] / c[i - 1] - 1 for i in range(max(1, len(c) - 63), len(c))]
    vol_ann = _stdev(rets) * (252 ** 0.5)
    va = ((pct_return(c, 63) or 0) / 100 / vol_ann) if vol_ann else 0
    vscore = clamp(50 + va * 18 - ((atr_rank if atr_rank is not None else 0.5) - 0.5) * 40)
    volatility = _cat(vscore, "σ-adj 3m ret %.2f · ATR%% %s (rank %.0f%% — calmer scores higher)"
                      % (va, "%.2f%%" % atrp if atrp else "n/a",
                         (atr_rank if atr_rank is not None else 0.5) * 100))
    return {"trend": trend, "rs": rs, "momentum": momentum, "volume": volume, "volatility": volatility}


def _options_category(sym, pcr_median=None):
    o = get_options(sym)
    if not o or o.get("error") or not o.get("pcrOI"):
        return None
    s, why = 50.0, []
    pcr = o["pcrOI"]
    # PCR is only meaningful RELATIVE to a baseline: preferred = z vs the
    # symbol's own accumulated history; fallback = vs today's sector median.
    # (Absolute anchors mis-read structurally hedged products — SPY sits ~2.5+.)
    if o.get("pcrZ") is not None:
        d = clamp(-o["pcrZ"] * 7, -14, 14)
        s += d
        why.append("P/C %.2f, z %+.1f vs own norm (%+.0f)" % (pcr, o["pcrZ"], d))
    elif pcr_median:
        d = clamp((pcr_median - pcr) / pcr_median * 25, -10, 10)
        s += d
        why.append("P/C %.2f vs sector median %.2f (%+.0f; own-history z calibrating %d/%d days)"
                   % (pcr, pcr_median, d, o.get("ivHistDays") or 0, OPT_HISTORY_DAYS_MIN))
    if o.get("netGEX") is not None:
        s += 8 if o["netGEX"] > 0 else -8
        why.append("net GEX %+.0fM$ (%s)" % (o["netGEX"], "stabilizing" if o["netGEX"] > 0 else "destabilizing"))
    if o.get("skew25d") is not None and o["skew25d"] > 6:
        s -= 7
        why.append("steep 25Δ skew %.1f (-7)" % o["skew25d"])
    if o.get("oiChangePct") is not None:
        d = clamp(o["oiChangePct"] * 2, -6, 6)
        s += d
        why.append("OI %+0.1f%% d/d (%+.0f)" % (o["oiChangePct"], d))
    return _cat(s, " · ".join(why))


def _macro_category(sym):
    drivers = []
    total = 0.0
    used = 0
    sec_bars = get_bars(sym)
    if not sec_bars:
        return None
    sc = [b["c"] for b in sec_bars]
    for proxy, infl in MACRO_INFLUENCE.items():
        pb = get_bars(proxy)
        if not pb:
            continue
        pc = [b["c"] for b in pb]
        r1m = pct_return(pc, 21)
        if r1m is None:
            continue
        corr = correlation(sc, pc, 63)
        if corr is None:
            continue
        # measured correlation × proxy trend = tailwind/headwind, nudged by the
        # domain map when it agrees in direction
        base = corr * clamp(r1m, -8, 8)
        if sym in infl["helps"] and r1m > 0:
            base += 0.5
        if sym in infl["hurts"] and r1m > 0:
            base -= 0.5
        total += base
        used += 1
        if abs(base) >= 0.4:
            drivers.append("%s %+.1f%%×ρ%+.2f" % (proxy, r1m, corr))
    if used < 3:
        return None
    drivers.sort(key=lambda s: -abs(float(s.split("×ρ")[0].split()[-1].rstrip("%"))))
    return _cat(50 + clamp(total * 6, -35, 35),
                "tailwind Σ(ρ×1m trend) over %d proxies: %s" % (used, "; ".join(drivers[:3]) or "flat"))


def sector_scores(weights_qs=None):
    w = dict(SCORE_WEIGHTS)
    if weights_qs:
        try:
            for pair in weights_qs.split(","):
                k, v = pair.split(":")
                if k.strip() in w:
                    w[k.strip()] = float(v)
        except ValueError:
            pass
    rot = cache_get("sectors", 120) or _cache_and_return("sectors", rotation)
    rotmap = {s["symbol"]: s for s in rot.get("sectors", []) if not s.get("warming")}
    breadth = rot.get("breadth") or {}
    out = {"warm": warm_status(), "weights": w, "sectors": [],
           "notes": ["options category: CBOE delayed chains, naive +call/−put GEX convention",
                     "news & ETF-flow categories intentionally excluded — no reliable free per-sector source",
                     "history sparkline uses the five bar-derived categories only"]}
    # pass 1: raw cross-sectional values for ranking
    raw = {}
    for sym, name in SECTORS:
        bars = get_bars(sym)
        r = rotmap.get(sym)
        if not bars or len(bars) < 210 or not r:
            continue
        blend = None
        if r.get("rs1m") is not None and r.get("rs3m") is not None:
            blend = 0.5 * r["rs1m"] + 0.3 * r["rs3m"] + 0.2 * (r.get("rs6m") or 0)
        av = atr(bars, 14)
        raw[sym] = {"bars": bars, "name": name, "rot": r, "blend": blend,
                    "atrp": (av / bars[-1]["c"] * 100) if av else None}
    blends = [v["blend"] for v in raw.values()]
    atrps = [v["atrp"] for v in raw.values()]
    spyc = _tf_closes(BENCH, "daily")
    pcrs = sorted(p for p in ((get_options(s) or {}).get("pcrOI") for s, _ in SECTORS) if p)
    pcr_median = pcrs[len(pcrs) // 2] if pcrs else None
    prev_scores = _scores_prev_day()
    for sym, v in raw.items():
        cats = _bar_categories(v["bars"], spyc, _pct_rank(blends, v["blend"]), _pct_rank(atrps, v["atrp"]))
        oc = _options_category(sym, pcr_median)
        if oc:
            cats["options"] = oc
        mc = _macro_category(sym)
        if mc:
            cats["macro"] = mc
        weighted = {k: cats[k] for k in cats if w.get(k)}
        avail_w = sum(w[k] for k in weighted)
        contribs = {k: {"score": weighted[k]["score"], "weight": w[k],
                        "contrib": round(w[k] / avail_w * weighted[k]["score"], 1),
                        "detail": weighted[k]["detail"],
                        "status": "validated (IC survives train/test)" if k == "rs"
                                  else "UNVALIDATED — provisional until snapshot history allows the IC test"}
                    for k in weighted}
        context = {k: {"score": cats[k]["score"], "weight": 0.0, "contrib": 0.0,
                       "detail": cats[k]["detail"], "status": CONTEXT_CATS.get(k, "context only")}
                   for k in cats if k not in weighted}
        total = round(sum(c["contrib"] for c in contribs.values()), 1)
        bull = round(sum(w[k] / avail_w * max(0.0, weighted[k]["score"] - 50) * 2 for k in weighted), 1)
        bear = round(sum(w[k] / avail_w * max(0.0, 50 - weighted[k]["score"]) * 2 for k in weighted), 1)
        scores_only = [weighted[k]["score"] for k in weighted]
        agree = 1 - min(1.0, _stdev(scores_only) / 35) if len(scores_only) > 1 else 0.5
        conf = round(100 * avail_w / sum(w.values()) * (0.5 + 0.5 * agree), 1)
        # risk (separate, higher = riskier): realized vol rank, drawdown, IV rank
        c = [b["c"] for b in v["bars"]]
        hi90 = max(c[-90:])
        dd = (hi90 - c[-1]) / hi90 * 100 if hi90 else 0
        o = get_options(sym) or {}
        ivr = o.get("ivRank")
        risk = clamp(45 * (_pct_rank(atrps, v["atrp"]) or 0.5) + min(30.0, dd * 2)
                     + (0.25 * ivr if ivr is not None else 0)
                     + (10 if v["rot"].get("quadrant") == "Lagging" else 0))
        stored = _scores_stored_series(sym)
        out["sectors"].append({
            "symbol": sym, "name": v["name"], "price": round(c[-1], 2),
            "total": total, "bull": bull, "bear": bear, "confidence": conf,
            "risk": round(risk, 1),
            "riskDetail": "ATR rank %.0f%% · 90d drawdown %.1f%% · IV rank %s · %s"
                          % ((_pct_rank(atrps, v["atrp"]) or 0.5) * 100, dd,
                             ("%.0f" % ivr) if ivr is not None else "n/a", v["rot"].get("quadrant")),
            "quadrant": v["rot"].get("quadrant"),
            "categories": contribs, "context": context,
            "delta1d": round(total - prev_scores[sym], 1) if sym in prev_scores else None,
            "history": stored if stored else _score_history(v["bars"], spyc),
            "historySource": "stored daily snapshots" if stored else "RS-blend trajectory (until snapshots accumulate)",
        })
    out["sectors"].sort(key=lambda s: -s["total"])
    out["regime"] = market_regime(rot)
    _scores_persist(out["sectors"])
    return out


# ── daily score snapshots: real history + day-over-day movers ────────────────
SCORES_HIST_PATH = os.path.join(os.environ.get("QUANTA_DATA", "") or
                                os.path.dirname(os.path.abspath(__file__)), "scores_history.json")
_scores_hist_lock = threading.Lock()


def _scores_hist_read():
    try:
        with open(SCORES_HIST_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _scores_persist(sectors):
    day = dt.date.today().isoformat()
    try:
        with _scores_hist_lock:
            hist = _scores_hist_read()
            row = {s["symbol"]: s["total"] for s in sectors}
            if hist.get(day) != row:
                hist[day] = row
                for d in sorted(hist)[:-120]:
                    del hist[d]
                os.makedirs(os.path.dirname(SCORES_HIST_PATH) or ".", exist_ok=True)
                with open(SCORES_HIST_PATH + ".tmp", "w") as f:
                    json.dump(hist, f)
                os.replace(SCORES_HIST_PATH + ".tmp", SCORES_HIST_PATH)
    except OSError:
        pass


def _scores_prev_day():
    with _scores_hist_lock:
        hist = _scores_hist_read()
    days = [d for d in sorted(hist) if d < dt.date.today().isoformat()]
    return hist[days[-1]] if days else {}


def _scores_stored_series(sym, min_days=5, max_days=30):
    with _scores_hist_lock:
        hist = _scores_hist_read()
    vals = [hist[d].get(sym) for d in sorted(hist)[-max_days:] if hist[d].get(sym) is not None]
    return vals if len(vals) >= min_days else None


def market_regime(rot):
    """Market-level context that scales HOW to read the scores (not who's best):
    breadth, vol trend, gamma regime, cyclical/defensive spread, active signals."""
    b = rot.get("breadth") or {}
    vix = get_bars("VIXY")
    v1m = pct_return([x["c"] for x in vix], 21) if vix else None
    spy_o = get_options(BENCH) or {}
    gex = spy_o.get("netGEX")
    sig = cache_get("signals", 120) or _cache_and_return("signals", signals)
    buys = [s["symbol"] for s in sig.get("sectors", []) if s.get("signal") == "BUY"]
    arming = [s["symbol"] for s in sig.get("sectors", []) if s.get("signal") == "Arming"]
    ready = []
    for sym, _n in SECTORS:
        a = analyze(sym)
        if a.get("ok") and a["status"] == "Ready":
            ready.append(sym)
    rotmap = {s["symbol"]: s for s in rot.get("sectors", []) if not s.get("warming")}
    defs = [rotmap[s]["rs1m"] for s in ("XLP", "XLU", "XLV") if s in rotmap and rotmap[s].get("rs1m") is not None]
    cycs = [rotmap[s]["rs1m"] for s in ("XLK", "XLY", "XLF", "XLI") if s in rotmap and rotmap[s].get("rs1m") is not None]
    spread = (sum(cycs) / len(cycs) - sum(defs) / len(defs)) if (defs and cycs) else None
    return {
        "breadthAbove50": "%d/%d" % (b.get("above50", 0), b.get("n", 0)) if b.get("n") else None,
        "ewMinusSpy1m": b.get("ewMinusSpy1m"),
        "volTrend1m": round(v1m, 1) if v1m is not None else None,
        "spyNetGEX": gex,
        "gammaRegime": ("positive (naive conv. — moves dampened)" if gex > 0
                        else "negative (naive conv. — moves amplified)") if gex is not None else None,
        "cycMinusDef1m": round(spread, 2) if spread is not None else None,
        "rsi2Buys": buys, "rsi2Arming": arming, "readySetups": ready,
        "note": "Mean-reversion BUYs fire on weakness by design — a low momentum "
                "category on a BUY sector is expected, not a contradiction.",
    }


_hist_cache = {}


def _score_history(bars, spyc, points=13, step=5):
    """Fallback sparkline until stored daily snapshots accumulate: the sector's
    RS blend vs SPY (the weight-bearing category) mapped to 0-100, weekly over
    ~a quarter. No lookahead; cached per (last-bar, count) — this was the most
    expensive part of /api/scores before caching."""
    ck = (bars[-1]["t"], len(bars))
    if ck in _hist_cache:
        return _hist_cache[ck]
    hist = []
    for k in range(points - 1, -1, -1):
        sub = [b["c"] for b in bars[:len(bars) - k * step]]
        ssub = spyc[:len(spyc) - k * step] if spyc else None
        if len(sub) < 150 or not ssub:
            hist.append(None)
            continue
        def rel(n):
            a, b = pct_return(sub, n), pct_return(ssub, n)
            return (a - b) if (a is not None and b is not None) else None
        r1, r3, r6 = rel(21), rel(63), rel(126)
        if r1 is None or r3 is None:
            hist.append(None)
            continue
        blend = 0.5 * r1 + 0.3 * r3 + 0.2 * (r6 or 0)
        hist.append(round(clamp(50 + blend * 6), 1))
    if len(_hist_cache) > 64:
        _hist_cache.clear()
    _hist_cache[ck] = hist
    return hist


def macro_view():
    """Macro proxies with measured trends + the sector-influence context notes."""
    rows = []
    for proxy, pname in MACRO_PROXIES:
        b = get_bars(proxy)
        infl = MACRO_INFLUENCE.get(proxy, {})
        if not b:
            rows.append({"symbol": proxy, "name": pname, "warming": True, "note": infl.get("note", "")})
            continue
        c = [x["c"] for x in b]
        rows.append({"symbol": proxy, "name": pname, "price": round(c[-1], 2),
                     "r1w": round(pct_return(c, 5) or 0, 2), "r1m": round(pct_return(c, 21) or 0, 2),
                     "r3m": round(pct_return(c, 63) or 0, 2),
                     "above50": bool(sma(c, 50) and c[-1] > sma(c, 50)),
                     "helps": infl.get("helps", []), "hurts": infl.get("hurts", []),
                     "note": infl.get("note", "")})
    # crude regime read: defensives-vs-cyclicals RS spread + vol trend
    rot = cache_get("sectors", 120) or _cache_and_return("sectors", rotation)
    rotmap = {s["symbol"]: s for s in rot.get("sectors", []) if not s.get("warming")}
    regime = None
    defs = [rotmap[s]["rs1m"] for s in ("XLP", "XLU", "XLV") if s in rotmap and rotmap[s].get("rs1m") is not None]
    cycs = [rotmap[s]["rs1m"] for s in ("XLK", "XLY", "XLF", "XLI") if s in rotmap and rotmap[s].get("rs1m") is not None]
    if defs and cycs:
        spread = sum(cycs) / len(cycs) - sum(defs) / len(defs)
        vix = next((r for r in rows if r["symbol"] == "VIXY" and not r.get("warming")), None)
        regime = {"cycMinusDef1m": round(spread, 2),
                  "read": ("risk-on: cyclicals leading defensives by %.1f%% (1m RS)" % spread) if spread > 0.5
                          else ("risk-off: defensives leading by %.1f%%" % -spread) if spread < -0.5
                          else "neutral: no clear cyclical/defensive leadership",
                  "volTrend": (vix or {}).get("r1m")}
    return {"proxies": rows, "regime": regime, "warm": warm_status(),
            "note": "All macro series are liquid-ETF proxies (free-tier honest): no direct 2Y/10Y/30Y or spot-VIX history. Treasury auctions not available on free feeds."}


# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH & PREDICTION ENGINE — runs on the bars already cached in memory.
# Answers "what has historically happened next under similar conditions?" with
# empirical distributions, Wilson confidence intervals and explicit sample
# sizes. 2 years of daily data is a SMALL sample; every view says so rather
# than presenting certainty. All classification uses backward-looking data only.
# ─────────────────────────────────────────────────────────────────────────────
CYCLICALS = ("XLK", "XLY", "XLF", "XLI")
DEFENSIVES = ("XLP", "XLU", "XLV")
_research_cache = {}


def _sector_matrix():
    """Date-aligned closes for the 11 sectors + SPY from cached bars."""
    spy_bars = get_bars(BENCH)
    if not spy_bars or len(spy_bars) < 300:
        return None
    def dts(bars):
        return [dt.datetime.fromtimestamp(b["t"] / 1000, dt.timezone.utc).date() for b in bars]
    per = {}
    for sym, _n in SECTORS:
        b = get_bars(sym)
        if not b:
            return None
        per[sym] = (b, dts(b))
    spy_d = dts(spy_bars)
    common = sorted(set(spy_d).intersection(*[set(d) for _b, d in per.values()]))
    if len(common) < 300:
        return None
    idx_spy = {d: i for i, d in enumerate(spy_d)}
    spy = [spy_bars[idx_spy[d]]["c"] for d in common]
    C = {}
    for sym, (b, d) in per.items():
        ix = {dd: i for i, dd in enumerate(d)}
        C[sym] = [b[ix[dd]]["c"] for dd in common]
    return {"dates": common, "C": C, "spy": spy}


def _ret(c, i, n):
    return (c[i] / c[i - n] - 1) * 100 if i - n >= 0 and c[i - n] else None


def regime_at(m, i):
    """Backward-looking regime label at day-index i of the aligned matrix."""
    spy, C = m["spy"], m["C"]
    if i < 260:
        return None
    s200 = sum(spy[i - 199:i + 1]) / 200
    above = spy[i] > s200
    r21 = _ret(spy, i, 21) or 0
    primary = (("Trending Bull" if r21 >= -1 else "Bull Pullback") if above
               else ("Bear Rally" if r21 > 1 else "Trending Bear"))
    rets = [spy[k] / spy[k - 1] - 1 for k in range(i - 20, i + 1)]
    vol = _stdev(rets) * (252 ** 0.5) * 100
    hist_vols = [_stdev([spy[k] / spy[k - 1] - 1 for k in range(j - 20, j + 1)]) * (252 ** 0.5) * 100
                 for j in range(260, i + 1, 21)]
    volpct = (sum(1 for v in hist_vols if v <= vol) / len(hist_vols)) if hist_vols else 0.5
    volmod = "high-vol" if volpct >= 0.8 else "low-vol" if volpct <= 0.3 else "mid-vol"
    def rel21(sym):
        a, b = _ret(C[sym], i, 21), _ret(spy, i, 21)
        return (a - b) if (a is not None and b is not None) else 0
    cyc = sum(rel21(s) for s in CYCLICALS) / len(CYCLICALS)
    dfs = sum(rel21(s) for s in DEFENSIVES) / len(DEFENSIVES)
    spread = cyc - dfs
    rot = "risk-on" if spread >= 0.5 else "defensive" if spread <= -0.5 else "mixed"
    breadth = sum(1 for s in C if i >= 49 and C[s][i] > sum(C[s][i - 49:i + 1]) / 50) / len(C)
    return {"primary": primary, "vol": volmod, "rotation": rot,
            "label": "%s · %s · %s" % (primary, volmod, rot),
            "evidence": {"spyVs200d": round((spy[i] / s200 - 1) * 100, 2), "spyRet21d": round(r21, 2),
                         "realizedVol": round(vol, 1), "volPercentile": round(volpct * 100),
                         "cycMinusDef21d": round(spread, 2), "breadthAbove50": round(breadth * 100)}}


def _weekly_states():
    """Weekly market-state snapshots (features + per-sector RS ranks + regime),
    cached per bar-set. Everything at week t uses only data ≤ t."""
    m = _sector_matrix()
    if not m:
        return None
    ck = ("weekly", len(m["dates"]), m["dates"][-1])
    if ck in _research_cache:
        return _research_cache[ck]
    spy, C, dates = m["spy"], m["C"], m["dates"]
    n = len(dates)
    states = []
    for i in range(260, n, 5):
        reg = regime_at(m, i)
        blends = {}
        for s in C:
            r1 = (_ret(C[s], i, 21) or 0) - (_ret(spy, i, 21) or 0)
            r3 = (_ret(C[s], i, 63) or 0) - (_ret(spy, i, 63) or 0)
            r6 = (_ret(C[s], i, 126) or 0) - (_ret(spy, i, 126) or 0)
            blends[s] = 0.5 * r1 + 0.3 * r3 + 0.2 * r6
        order = sorted(blends, key=blends.get, reverse=True)
        rank = {s: k for k, s in enumerate(order)}      # 0 = strongest
        # avg pairwise sector correlation over 21d (correlation structure)
        rmat = {s: [C[s][k] / C[s][k - 1] - 1 for k in range(i - 20, i + 1)] for s in C}
        syms = list(C)
        cors = []
        for a in range(len(syms)):
            for b in range(a + 1, len(syms)):
                r1_, r2_ = rmat[syms[a]], rmat[syms[b]]
                m1, m2 = sum(r1_) / len(r1_), sum(r2_) / len(r2_)
                cv = sum((x - m1) * (y - m2) for x, y in zip(r1_, r2_))
                v1 = sum((x - m1) ** 2 for x in r1_) ** 0.5
                v2 = sum((y - m2) ** 2 for y in r2_) ** 0.5
                if v1 > 0 and v2 > 0:
                    cors.append(cv / (v1 * v2))
        states.append({
            "i": i, "date": dates[i].isoformat(), "regime": reg,
            "blends": blends, "rank": rank,
            "features": {"breadth": reg["evidence"]["breadthAbove50"],
                         "spyR21": reg["evidence"]["spyRet21d"],
                         "spyR63": _ret(spy, i, 63) or 0,
                         "volPct": reg["evidence"]["volPercentile"],
                         "cycDef": reg["evidence"]["cycMinusDef21d"],
                         "avgCorr": round(sum(cors) / len(cors), 3) if cors else None,
                         "ewSpy21": round(sum(((_ret(C[s], i, 21) or 0) - (_ret(spy, i, 21) or 0))
                                              for s in C) / len(C), 2)},
        })
    out = {"m": m, "states": states}
    if len(_research_cache) > 8:
        _research_cache.clear()
    _research_cache[ck] = out
    return out


def _fwd_rel(m, sym, i, h):
    spy, c = m["spy"], m["C"][sym]
    if i + h >= len(c):
        return None
    return (c[i + h] / c[i] - 1) * 100 - (spy[i + h] / spy[i] - 1) * 100


def _wilson(p, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    den = 1 + z * z / n
    ctr = p + z * z / (2 * n)
    rad = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (ctr - rad) / den), min(1.0, (ctr + rad) / den)


RANK_GROUPS = [("Top-3 RS", 0, 2), ("Mid (4-8)", 3, 7), ("Bottom-3 RS", 8, 10)]


def probabilities_view():
    """Empirical P(sector beats SPY over h days | its current RS rank group),
    pooled across all sectors and weeks. Overlapping windows inflate n, so the
    effective sample is ~n/(h/5) — both numbers are reported."""
    ws = _weekly_states()
    if not ws:
        return {"error": "bars still warming"}
    m, states = ws["m"], ws["states"]
    table = []
    for gname, lo, hi in RANK_GROUPS:
        row = {"group": gname, "horizons": {}}
        for h in (5, 10, 21, 60):
            obs = []
            for st in states:
                for s, rk in st["rank"].items():
                    if lo <= rk <= hi:
                        f = _fwd_rel(m, s, st["i"], h)
                        if f is not None:
                            obs.append(f)
            if len(obs) < 20:
                row["horizons"][str(h)] = None
                continue
            wins = sum(1 for o in obs if o > 0)
            p = wins / len(obs)
            ci = _wilson(p, max(1, int(len(obs) / max(1, h / 5))))   # CI on effective n
            so = sorted(obs)
            wl = [o for o in obs if o > 0]
            ll = [o for o in obs if o <= 0]
            row["horizons"][str(h)] = {
                "p": round(p * 100, 1), "ciLo": round(ci[0] * 100, 1), "ciHi": round(ci[1] * 100, 1),
                "median": round(so[len(so) // 2], 2), "q25": round(so[len(so) // 4], 2),
                "q75": round(so[3 * len(so) // 4], 2), "n": len(obs),
                "nEff": max(1, int(len(obs) / max(1, h / 5))),
                "avgWin": round(sum(wl) / len(wl), 2) if wl else None,
                "avgLoss": round(sum(ll) / len(ll), 2) if ll else None,
            }
        table.append(row)
    cur = {}
    last = states[-1]
    for s, rk in last["rank"].items():
        cur[s] = next(g for g, lo, hi in RANK_GROUPS if lo <= rk <= hi)
    return {"table": table, "currentGroup": cur, "asOf": last["date"],
            "note": "Pooled 11 sectors × %d weeks (2yr — small sample). CI uses the overlap-adjusted "
                    "effective n. These are historical base rates, not forecasts." % len(states)}


def regime_view():
    ws = _weekly_states()
    if not ws:
        return {"error": "bars still warming"}
    m, states = ws["m"], ws["states"]
    cur = regime_at(m, len(m["dates"]) - 1)
    freq = {}
    for st in states:
        freq[st["regime"]["primary"]] = freq.get(st["regime"]["primary"], 0) + 1
    # per-regime historical sector winners/losers (forward 21d SPY-relative)
    perf = {}
    for st in states:
        r = st["regime"]["primary"]
        for s in st["blends"]:
            f = _fwd_rel(m, s, st["i"], 21)
            if f is not None:
                perf.setdefault(r, {}).setdefault(s, []).append(f)
    hist = {}
    for r, d in perf.items():
        rows = sorted(((s, sum(v) / len(v), len(v)) for s, v in d.items()), key=lambda x: -x[1])
        hist[r] = {"weeks": freq.get(r, 0),
                   "winners": [{"symbol": s, "avgRel21": round(a, 2), "n": n} for s, a, n in rows[:3]],
                   "losers": [{"symbol": s, "avgRel21": round(a, 2), "n": n} for s, a, n in rows[-3:]]}
    # confidence: margins from the rule boundaries
    ev = cur["evidence"]
    margins = [min(1.0, abs(ev["spyVs200d"]) / 3), min(1.0, abs(ev["spyRet21d"] + 1) / 3
               if cur["primary"] in ("Trending Bull", "Bull Pullback") else abs(ev["spyRet21d"] - 1) / 3),
               min(1.0, abs(ev["volPercentile"] - 55) / 45)]
    conf = round(100 * sum(margins) / len(margins))
    return {"current": cur, "confidence": conf,
            "frequencies": {r: {"weeks": c, "pct": round(100 * c / len(states), 1)} for r, c in freq.items()},
            "historical": hist, "sampleWeeks": len(states),
            "note": "Rule-based, backward-looking only. 2yr sample: regime stats with few weeks are anecdotes, "
                    "not statistics — n is shown everywhere."}


def analogs_view(k=8):
    """Nearest historical market states to today (z-scored features, euclidean),
    excluding the last 4 weeks, with what happened next."""
    ws = _weekly_states()
    if not ws:
        return {"error": "bars still warming"}
    m, states = ws["m"], ws["states"]
    keys = ["breadth", "spyR21", "spyR63", "volPct", "cycDef", "avgCorr", "ewSpy21"]
    vals = {kk: [st["features"][kk] for st in states if st["features"][kk] is not None] for kk in keys}
    mu = {kk: sum(v) / len(v) for kk, v in vals.items() if v}
    sd = {kk: (_stdev(v) or 1) for kk, v in vals.items() if v}
    def zvec(st):
        return [((st["features"][kk] or mu[kk]) - mu[kk]) / sd[kk] for kk in keys]
    today = states[-1]
    tz = zvec(today)
    cands = []
    for st in states[:-4]:
        d = sum((a - b) ** 2 for a, b in zip(zvec(st), tz)) ** 0.5
        cands.append((d, st))
    cands.sort(key=lambda x: x[0])
    rows, spy10, spy21, top3rel = [], [], [], []
    spy = m["spy"]
    for d, st in cands[:k]:
        i = st["i"]
        f10 = ((spy[i + 10] / spy[i] - 1) * 100) if i + 10 < len(spy) else None
        f21 = ((spy[i + 21] / spy[i] - 1) * 100) if i + 21 < len(spy) else None
        top3 = [s for s, rk in st["rank"].items() if rk <= 2]
        t3 = [x for x in (_fwd_rel(m, s, i, 21) for s in top3) if x is not None]
        t3m = sum(t3) / len(t3) if t3 else None
        rows.append({"date": st["date"], "distance": round(d, 2), "regime": st["regime"]["label"],
                     "top3Then": top3, "spyFwd10": round(f10, 2) if f10 is not None else None,
                     "spyFwd21": round(f21, 2) if f21 is not None else None,
                     "top3FwdRel21": round(t3m, 2) if t3m is not None else None})
        if f10 is not None:
            spy10.append(f10)
        if f21 is not None:
            spy21.append(f21)
        if t3m is not None:
            top3rel.append(t3m)
    def agg(v):
        if not v:
            return None
        sv = sorted(v)
        return {"win": round(100 * sum(1 for x in v if x > 0) / len(v)), "median": round(sv[len(sv) // 2], 2),
                "worst": round(sv[0], 2), "best": round(sv[-1], 2), "n": len(v)}
    return {"today": {"date": today["date"], "features": today["features"], "regime": today["regime"]["label"]},
            "analogs": rows,
            "aggregate": {"spyFwd10": agg(spy10), "spyFwd21": agg(spy21), "top3ContinuationRel21": agg(top3rel)},
            "note": "%d nearest of %d weeks by z-scored state distance — one 2yr regime cycle, so analogs "
                    "describe THIS sample, not all of history." % (k, len(states) - 4)}


def research_view():
    """Validation of the production signal, live: rolling IC, IC by regime
    (the adaptive-weighting test), and RS rank-group monotonicity."""
    ws = _weekly_states()
    if not ws:
        return {"error": "bars still warming"}
    m, states = ws["m"], ws["states"]
    ics = []
    for st in states:
        xs, ys = [], []
        for s, bl in st["blends"].items():
            f = _fwd_rel(m, s, st["i"], 10)
            if f is not None:
                xs.append(bl)
                ys.append(f)
        if len(xs) >= 8:
            n = len(xs)
            rx = sorted(range(n), key=lambda a: xs[a])
            ry = sorted(range(n), key=lambda a: ys[a])
            rkx, rky = [0] * n, [0] * n
            for r_, a in enumerate(rx):
                rkx[a] = r_
            for r_, a in enumerate(ry):
                rky[a] = r_
            mx = sum(rkx) / n
            cov = sum((rkx[a] - mx) * (rky[a] - mx) for a in range(n))
            var = sum((rkx[a] - mx) ** 2 for a in range(n))
            ics.append({"date": st["date"], "ic": round(cov / var, 3) if var else None,
                        "regime": st["regime"]["primary"]})
    roll = []
    vals = [x["ic"] for x in ics if x["ic"] is not None]
    for j in range(12, len(ics)):
        w = [x["ic"] for x in ics[j - 12:j + 1] if x["ic"] is not None]
        roll.append({"date": ics[j]["date"], "ic13w": round(sum(w) / len(w), 3) if w else None})
    by_reg = {}
    for x in ics:
        if x["ic"] is not None:
            by_reg.setdefault(x["regime"], []).append(x["ic"])
    regs = []
    for r, v in sorted(by_reg.items(), key=lambda kv: -len(kv[1])):
        mn, se, n = (sum(v) / len(v), (_stdev(v) / len(v) ** 0.5) if len(v) > 2 else None, len(v))
        regs.append({"regime": r, "n": n, "meanIC": round(mn, 3),
                     "tStat": round(mn / se, 1) if se else None})
    enough = [r for r in regs if r["n"] >= 30]
    verdict = ("ADAPTIVE WEIGHTING NOT JUSTIFIED YET: no regime has n≥30 weekly ICs (largest bucket n=%d) — "
               "per-regime differences are indistinguishable from noise at this sample size. Static weights stay; "
               "re-run as history accumulates." % (max((r["n"] for r in regs), default=0))
               if not enough else
               "Buckets with n≥30 exist — compare their mean ICs before considering adaptive weights.")
    return {"weeklyIC": ics[-26:], "rollingIC": roll, "icOverall": round(sum(vals) / len(vals), 3) if vals else None,
            "byRegime": regs, "adaptiveWeightingVerdict": verdict,
            "note": "RS blend vs forward 10d SPY-relative return, Spearman per week (11 sectors). "
                    "This is the LIVE version of research_categories.py's test."}


def opportunities_view():
    sc = cache_get("scores", 120) or _cache_and_return("scores", sector_scores)
    prob = probabilities_view()
    reg = regime_view()
    if prob.get("error") or reg.get("error"):
        return {"error": "warming"}
    ptab = {r["group"]: r["horizons"].get("10") for r in prob.get("table", [])}
    cur_reg = reg["current"]["primary"]
    regperf = {w["symbol"]: (w["avgRel21"], w["n"]) for w in
               reg["historical"].get(cur_reg, {}).get("winners", []) +
               reg["historical"].get(cur_reg, {}).get("losers", [])}
    rows = []
    for s in sc.get("sectors", []):
        grp = prob["currentGroup"].get(s["symbol"])
        p10 = ptab.get(grp)
        evidence = ["composite %s (rs-weighted, conf %s%%)" % (s["total"], s["confidence"]),
                    "RS group: %s → historical P(beat SPY 10d) %s%% [%s–%s], median %+0.2f%%"
                    % (grp, p10["p"], p10["ciLo"], p10["ciHi"], p10["median"]) if p10 else "probability table warming"]
        conflicts = []
        cats = s.get("categories", {})
        if cats.get("options", {}).get("score", 50) < 45 and s["total"] >= 55:
            conflicts.append("options positioning bearish (%s) vs strong composite: %s"
                             % (cats["options"]["score"], cats["options"]["detail"]))
        if cats.get("macro", {}).get("score", 50) < 42 and s["total"] >= 55:
            conflicts.append("macro headwind (%s): %s" % (cats["macro"]["score"], cats["macro"]["detail"]))
        if s.get("risk", 0) >= 60:
            conflicts.append("elevated risk score %s (%s)" % (s["risk"], s.get("riskDetail", "")))
        rp = regperf.get(s["symbol"])
        fit = None
        if rp:
            fit = {"avgRel21": rp[0], "n": rp[1], "regime": cur_reg}
            (evidence if rp[0] > 0 else conflicts).append(
                "in %s weeks this sector averaged %+0.2f%% vs SPY fwd 21d (n=%d)" % (cur_reg, rp[0], rp[1]))
        rows.append({"symbol": s["symbol"], "name": s["name"], "score": s["total"],
                     "pBeat10d": p10["p"] if p10 else None, "group": grp,
                     "risk": s["risk"], "confidence": s["confidence"], "delta1d": s.get("delta1d"),
                     "regimeFit": fit, "evidence": evidence, "conflicts": conflicts})
    rows.sort(key=lambda r: -r["score"])
    return {"regime": cur_reg, "rows": rows,
            "note": "Ranked by the evidence-weighted composite; probability and regime-fit columns are "
                    "historical base rates with n shown — context, not forecasts."}


# ─────────────────────────────────────────────────────────────────────────────
# FACTOR INTELLIGENCE — which measurable drivers explain each sector, how
# stable those relationships are, and whether they're strengthening or
# breaking. Attribution is UNIVARIATE (beta × factor move per factor):
# factors overlap, so contributions don't sum to the sector's move — the
# residual is shown, never hidden. No free source exists for real yields,
# CPI-surprise series, ISM, or credit-spread indices, so the factor library is
# liquid-ETF proxies + market-structure series derived from our own bars;
# adding a factor = one line in FACTOR_DEFS.
# ─────────────────────────────────────────────────────────────────────────────
FACTOR_DEFS = [
    ("TLT", "Rates (long Treasuries — up = yields down)"),
    ("UUP", "US Dollar"),
    ("USO", "Crude Oil"),
    ("GLD", "Gold"),
    ("CPER", "Copper / global growth"),
    ("VIXY", "Volatility regime"),
    ("HYG", "Credit / risk appetite"),
    ("RSPvSPY", "Equal-weight vs cap-weight (breadth)"),
    ("IWMvSPY", "Small vs large caps"),
    ("QQQvSPY", "Growth / mega-cap-tech leadership"),
]
FACTOR_RATIOS = {"RSPvSPY": ("RSP", None), "IWMvSPY": ("IWM", None), "QQQvSPY": ("QQQ", None)}


def _factor_matrix():
    m = _sector_matrix()
    if not m:
        return None
    ck = ("factors", len(m["dates"]), m["dates"][-1])
    if ck in _research_cache:
        return _research_cache[ck]
    dates = m["dates"]

    def series_for(sym):
        b = get_bars(sym)
        if not b:
            return None
        dmap = {dt.datetime.fromtimestamp(x["t"] / 1000, dt.timezone.utc).date(): x["c"] for x in b}
        out, last, miss = [], None, 0
        for d in dates:
            v = dmap.get(d)
            if v is None:
                miss += 1
            else:
                last = v
            out.append(last)
        if miss > len(dates) * 0.3:
            return None                     # too sparse to trust
        first = next((v for v in out if v is not None), None)
        return [v if v is not None else first for v in out]

    F = {}
    for fid, _name in FACTOR_DEFS:
        if fid in FACTOR_RATIOS:
            num = series_for(FACTOR_RATIOS[fid][0])
            F[fid] = [a / b for a, b in zip(num, m["spy"])] if num else None
        else:
            F[fid] = series_for(fid)
    F = {k: v for k, v in F.items() if v}
    out = {"m": m, "F": F, "names": dict(FACTOR_DEFS)}
    _research_cache[ck] = out
    return out


def _beta_corr(cs, cf, i, w=63):
    """(beta, corr) of sector returns on factor returns over w days ending at i."""
    if i - w < 1:
        return None, None
    rs = [cs[k] / cs[k - 1] - 1 for k in range(i - w + 1, i + 1)]
    rf = [cf[k] / cf[k - 1] - 1 for k in range(i - w + 1, i + 1)]
    ms, mf = sum(rs) / w, sum(rf) / w
    cov = sum((a - ms) * (b - mf) for a, b in zip(rs, rf)) / w
    vf = sum((b - mf) ** 2 for b in rf) / w
    vs = sum((a - ms) ** 2 for a in rs) / w
    beta = cov / vf if vf > 0 else None
    corr = cov / ((vs ** 0.5) * (vf ** 0.5)) if vs > 0 and vf > 0 else None
    return beta, corr


def factors_view():
    fm = _factor_matrix()
    if not fm:
        return {"error": "bars still warming"}
    m, F, names = fm["m"], fm["F"], fm["names"]
    i = len(m["dates"]) - 1
    # factor trends + historical sign-persistence (P the 21d trend keeps its sign)
    factors = {}
    for fid, cf in F.items():
        t21 = (cf[i] / cf[i - 21] - 1) * 100 if cf[i - 21] else 0
        same = tot = 0
        for j in range(260, i - 21, 5):
            a = cf[j] / cf[j - 21] - 1
            b = cf[j + 21] / cf[j] - 1
            if abs(a) > 1e-9:
                tot += 1
                same += (a > 0) == (b > 0)
        factors[fid] = {"name": names[fid], "trend21": round(t21, 2),
                        "pPersist": round(100 * same / tot) if tot >= 20 else None, "nPersist": tot}
    sectors, flags = [], []
    for sym, _n in SECTORS:
        cs = m["C"][sym]
        sec21 = (cs[i] / cs[i - 21] - 1) * 100
        rows = []
        for fid, cf in F.items():
            beta, corr = _beta_corr(cs, cf, i)
            _b2, prior = _beta_corr(cs, cf, i - 63)
            if beta is None or corr is None:
                continue
            f21 = factors[fid]["trend21"]
            contrib = beta * f21
            dcorr = (corr - prior) if prior is not None else None
            rows.append({"factor": fid, "name": names[fid], "beta": round(beta, 2),
                         "corr63": round(corr, 2), "corrPrior63": round(prior, 2) if prior is not None else None,
                         "deltaCorr": round(dcorr, 2) if dcorr is not None else None,
                         "factorTrend21": f21, "contrib21": round(contrib, 2),
                         "pPersist": factors[fid]["pPersist"]})
            if dcorr is not None and abs(dcorr) >= 0.4:
                flags.append("%s sensitivity to %s shifted %+.2f → %+.2f over the last quarter (Δ%+.2f)"
                             % (sym, fid, prior, corr, dcorr))
        rows.sort(key=lambda r: -abs(r["contrib21"]))
        thresh = max(0.15, abs(sec21) * 0.2)
        primary = [r for r in rows if abs(r["contrib21"]) >= thresh and r["contrib21"] * sec21 > 0
                   and abs(r["corr63"]) >= 0.25][:3]
        conflicting = [r for r in rows if abs(r["contrib21"]) >= thresh and r["contrib21"] * sec21 < 0
                       and abs(r["corr63"]) >= 0.25][:3]
        used = {r["factor"] for r in primary + conflicting}
        supporting = [r for r in rows if r["factor"] not in used and abs(r["corr63"]) >= 0.25][:3]
        weak = [r["factor"] for r in rows if abs(r["corr63"]) < 0.2]
        explained = sum(r["contrib21"] for r in rows)
        top = primary + conflicting
        stab = 1 - min(1.0, sum(abs(r["deltaCorr"] or 0) for r in top) / max(1, len(top)) / 0.6) if top else 0.3
        strength = sum(abs(r["corr63"]) for r in top) / max(1, len(top)) if top else 0.0
        conf = round(100 * min(1.0, strength * 1.6) * (0.5 + 0.5 * stab))
        sectors.append({"symbol": sym, "move21": round(sec21, 2),
                        "explained21": round(explained, 2), "residual21": round(sec21 - explained, 2),
                        "primary": primary, "conflicting": conflicting, "supporting": supporting,
                        "weak": weak, "confidence": conf})
    return {"asOf": m["dates"][i].isoformat(), "factors": factors, "sectors": sectors,
            "stabilityFlags": flags,
            "note": "Univariate beta attribution over 63d returns — factors overlap, so contributions don't "
                    "sum to the move (residual shown). ΔCorr compares the last 63d vs the prior 63d; |Δ|≥0.4 is "
                    "flagged as a relationship break. pPersist = historical P(21d factor trend keeps its sign "
                    "another 21d). Proxies only — real yields/CPI/ISM/credit-spread indices have no free source."}


# ── Edge Discovery Lab — automated condition search on the weekly states ─────
EDGE_CONDS = [
    ("breadth ≥ 70%", lambda f: (f["breadth"] or 0) >= 70),
    ("breadth ≤ 40%", lambda f: (f["breadth"] or 100) <= 40),
    ("vol pctile ≥ 80", lambda f: (f["volPct"] or 0) >= 80),
    ("vol pctile ≤ 30", lambda f: (f["volPct"] or 100) <= 30),
    ("risk-on (cyc−def > 0.5%)", lambda f: (f["cycDef"] or 0) > 0.5),
    ("defensive (cyc−def < −0.5%)", lambda f: (f["cycDef"] or 0) < -0.5),
    ("EW beating SPY (1m)", lambda f: (f["ewSpy21"] or 0) > 0),
    ("EW lagging SPY (1m)", lambda f: (f["ewSpy21"] or 0) < 0),
    ("SPY 21d up", lambda f: (f["spyR21"] or 0) > 0),
    ("SPY 21d down", lambda f: (f["spyR21"] or 0) < 0),
    ("high sector corr (≥0.6)", lambda f: (f["avgCorr"] or 0) >= 0.6),
    ("low sector corr (≤0.35)", lambda f: (f["avgCorr"] or 1) <= 0.35),
]


def edge_lab():
    ws = _weekly_states()
    if not ws:
        return {"error": "bars still warming"}
    m, states = ws["m"], ws["states"]
    spy = m["spy"]

    def spy_fwd10(st):
        i = st["i"]
        return (spy[i + 10] / spy[i] - 1) * 100 if i + 10 < len(spy) else None

    def top3_cont21(st):
        t3 = [x for x in (_fwd_rel(m, s, st["i"], 21) for s, rk in st["rank"].items() if rk <= 2)
              if x is not None]
        return sum(t3) / len(t3) if t3 else None

    targets = [("SPY fwd 10d %", spy_fwd10), ("top-3 RS continuation, rel 21d %", top3_cont21)]
    split = int(len(states) * 0.6)
    combos = [((na,), (ca,)) for na, ca in EDGE_CONDS] + \
             [((EDGE_CONDS[a][0], EDGE_CONDS[b][0]), (EDGE_CONDS[a][1], EDGE_CONDS[b][1]))
              for a in range(len(EDGE_CONDS)) for b in range(a + 1, len(EDGE_CONDS))]

    def stats(vals):
        n = len(vals)
        if n < 5:
            return None
        mn = sum(vals) / n
        sd = _stdev(vals)
        gp = sum(v for v in vals if v > 0)
        gl = -sum(v for v in vals if v <= 0)
        return {"n": n, "mean": round(mn, 2), "win": round(100 * sum(1 for v in vals if v > 0) / n),
                "pf": round(gp / gl, 2) if gl > 0 else None,
                "t": round(mn / (sd / n ** 0.5), 1) if sd > 0 else None,
                "worst": round(min(vals), 2)}

    tested, survivors = 0, []
    for tname, tfn in targets:
        base_all = [v for v in (tfn(st) for st in states) if v is not None]
        base = stats(base_all)
        for names_, fns in combos:
            tr, te = [], []
            for k, st in enumerate(states):
                if all(fn(st["features"]) for fn in fns):
                    v = tfn(st)
                    if v is not None:
                        (tr if k < split else te).append(v)
            tested += 1
            str_, ste = stats(tr), stats(te)
            if (str_ and ste and str_["n"] >= 12 and ste["n"] >= 8
                    and str_["mean"] > 0 and ste["mean"] > 0 and (str_["t"] or 0) >= 1.5
                    and base and str_["mean"] > base["mean"]):
                survivors.append({"condition": " AND ".join(names_), "target": tname,
                                  "train": str_, "test": ste,
                                  "baseline": {"mean": base["mean"], "n": base["n"]}})
    survivors.sort(key=lambda s: -(s["test"]["mean"] or 0))
    return {"tested": tested, "survivors": survivors[:10], "survivorCount": len(survivors),
            "weeks": len(states),
            "note": "Gate: train n≥12 & test n≥8, mean>0 in BOTH windows, train t≥1.5, and train mean above "
                    "the unconditional baseline. %d combinations were tested — at these thresholds several "
                    "false positives are EXPECTED by chance (multiple comparisons on ~100 weeks). Survivors are "
                    "watchlist candidates to re-verify as new data arrives, not tradable edges." % (
                        len(combos) * len(targets))}


# ── Research Control Center — the state of every signal in one payload ───────
RESEARCH_BACKLOG = [
    "Longer daily history (10y import) — multiplies power of every engine",
    "Options-category IC test — needs ~60 snapshot days",
    "Volatility-inverted (high-beta) category — pre-registered, test on new data only",
    "IV-rank filter on RSI(2) entries — needs IV history",
    "Regime-conditional RSI(2) expectancy — needs journal trades",
    "Analog-engine feature weighting — needs >100 weeks",
    "GEX-change → sector-swing predictiveness — needs snapshot history",
]


def registry_view():
    rv = cache_get("research", 600) or _cache_and_return("research", research_view)
    roll = [x["ic13w"] for x in (rv.get("rollingIC") or []) if x.get("ic13w") is not None]
    rs_live = {"overallIC": rv.get("icOverall"), "rolling13w": roll[-1] if roll else None,
               "degrading": bool(roll and rv.get("icOverall") and roll[-1] < 0 <= rv["icOverall"])}
    opt_days = max(((get_options(s) or {}).get("ivHistDays") or 0) for s in OPTIONS_UNIVERSE) \
        if any(get_options(s) for s in OPTIONS_UNIVERSE) else 0
    with _scores_hist_lock:
        score_days = len(_scores_hist_read())
    with _state_lock:
        n_closed = len(_state["closed"])
        n_open = len(_state["positions"])
    models = [
        {"name": "RSI(2) mean-reversion (Signals)", "stage": "production",
         "evidence": "walk-forward OOS: 74.7% win, PF 2.05, n=87 (research.py)",
         "monitoring": "live daily; regime-expectancy pending journal trades"},
        {"name": "RS rotation top-3/1m (Rotation model)", "stage": "production",
         "evidence": "train PF 2.88 → test PF 2.92, 67% win, n=30 (small sample)",
         "monitoring": "weekly IC %.3f overall · rolling13w %s%s" % (
             rs_live["overallIC"] or 0, rs_live["rolling13w"],
             " · ⚠ DEGRADING (rolling<0)" if rs_live["degrading"] else "")},
        {"name": "Composite: rs category (w 0.70)", "stage": "production",
         "evidence": "IC +0.031 train / +0.017 test; only ablation survivor",
         "monitoring": "continuous (Research tab rolling IC)"},
        {"name": "Composite: options category (w 0.15)", "stage": "validation",
         "evidence": "UNVALIDATED — %d/60 snapshot days toward the IC test" % opt_days,
         "monitoring": "PCR z calibrating (%d/20 days)" % opt_days},
        {"name": "Composite: macro category (w 0.15)", "stage": "validation",
         "evidence": "UNVALIDATED — corr×trend construction, no history for IC test yet",
         "monitoring": "factor-stability flags act as an early warning"},
        {"name": "trend / momentum / volume categories", "stage": "retired",
         "evidence": "failed IC validation (train −0.03/−0.06/−0.16); trend ρ0.81-redundant with rs",
         "monitoring": "displayed as zero-weight context"},
        {"name": "volatility category", "stage": "retired",
         "evidence": "wrong-signed as selection (IC21 −0.213, t −4.8)",
         "monitoring": "inverted version pre-registered for future data"},
        {"name": "Intraday futures signals", "stage": "retired",
         "evidence": "no combo positive in both train and test net of costs (research_futures.py)",
         "monitoring": "Futures tab is context-only by design"},
    ]
    # model disagreement per sector — conflicting models are information
    sc = cache_get("scores", 120) or _cache_and_return("scores", sector_scores)
    sig = cache_get("signals", 120) or _cache_and_return("signals", signals)
    sigmap = {s["symbol"]: s.get("signal") for s in sig.get("sectors", []) if not s.get("warming")}
    disagree = []
    for s in sc.get("sectors", []):
        cats = s.get("categories", {})
        votes = {"rs": 1 if cats.get("rs", {}).get("score", 50) >= 60 else -1 if cats.get("rs", {}).get("score", 50) <= 40 else 0,
                 "options": 1 if cats.get("options", {}).get("score", 50) >= 55 else -1 if cats.get("options", {}).get("score", 50) <= 45 else 0,
                 "macro": 1 if cats.get("macro", {}).get("score", 50) >= 55 else -1 if cats.get("macro", {}).get("score", 50) <= 45 else 0,
                 "meanRev": 1 if sigmap.get(s["symbol"]) in ("BUY", "Arming") else 0}
        nz = [v for v in votes.values() if v != 0]
        d = round(_stdev(nz), 2) if len(nz) > 1 else 0.0
        disagree.append({"symbol": s["symbol"], "votes": votes, "disagreement": d})
    disagree.sort(key=lambda x: -x["disagreement"])
    return {"models": models,
            "dataQuality": {"bars": warm_status(), "optionsSnapshotDays": opt_days,
                            "scoreHistoryDays": score_days, "journalClosedTrades": n_closed,
                            "openPositions": n_open},
            "disagreement": disagree, "backlog": RESEARCH_BACKLOG,
            "note": "Stages: idea → testing → validation → production → monitoring → retirement. Nothing holds "
                    "composite weight without surviving train/test; retired items stay visible with the reason."}


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO CONSTRUCTION & DECISION ENGINE — converts the research outputs
# (scores, probabilities, regime, factor betas, analogs) into an explainable
# suggested allocation, position-sizing methods, factor exposures, and a
# scenario simulator. This is a DECISION-SUPPORT FRAMEWORK with every number
# traceable to a shown method — not advice, and it says so. Expected returns
# are historical base-rate medians; scenario impacts are linear factor-beta
# approximations; both caveats ride along in the payloads.
# ─────────────────────────────────────────────────────────────────────────────
ALLOC_MAX_POS = 0.25          # single-sector cap
ALLOC_REGIME_INVEST = {       # invested fraction by primary regime (heuristic, labeled)
    "Trending Bull": 0.90, "Bull Pullback": 0.75, "Bear Rally": 0.50, "Trending Bear": 0.30,
}


def _sector_vol(sym, days=63):
    b = get_bars(sym)
    if not b or len(b) < days + 1:
        return None
    c = [x["c"] for x in b][-(days + 1):]
    rets = [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    return _stdev(rets) * (252 ** 0.5)


def _factor_betas():
    """{sector: {factor: beta}} from the cached factor engine."""
    fx = cache_get("factors", 600) or _cache_and_return("factors", factors_view)
    if fx.get("error"):
        return {}
    out = {}
    for s in fx.get("sectors", []):
        rows = s.get("primary", []) + s.get("conflicting", []) + s.get("supporting", [])
        seen = {}
        for r in rows:
            seen[r["factor"]] = r["beta"]
        out[s["symbol"]] = seen
    return out


def allocation_view():
    opps = cache_get("opps", 300) or _cache_and_return("opps", opportunities_view)
    reg = cache_get("regime", 600) or _cache_and_return("regime", regime_view)
    prob = cache_get("probs", 600) or _cache_and_return("probs", probabilities_view)
    if opps.get("error") or reg.get("error") or prob.get("error"):
        return {"error": "engines warming"}
    primary = reg["current"]["primary"]
    invest = ALLOC_REGIME_INVEST.get(primary, 0.5)
    if reg["current"]["vol"] == "high-vol":
        invest = max(0.2, invest - 0.15)
    ptab = {r["group"]: r["horizons"].get("10") for r in prob.get("table", [])}
    included, excluded = [], []
    for o in opps.get("rows", []):
        p10 = o.get("pBeat10d")
        why_not = []
        if o["score"] < 55:
            why_not.append("composite %s < 55" % o["score"])
        if p10 is not None and p10 <= 50:
            why_not.append("historical P(beat SPY 10d) %s%% ≤ 50%%" % p10)
        if o["risk"] >= 70:
            why_not.append("risk score %s ≥ 70" % o["risk"])
        if why_not:
            excluded.append({"symbol": o["symbol"], "reasons": why_not})
            continue
        vol = _sector_vol(o["symbol"])
        conviction = (o["score"] - 50) / 50 * (o["confidence"] / 100)
        included.append({"o": o, "vol": vol or 0.2, "conviction": conviction, "p10": p10})
    total_raw = sum(c["conviction"] / c["vol"] for c in included) or 1
    rows = []
    for c in included:
        w = min(ALLOC_MAX_POS, (c["conviction"] / c["vol"]) / total_raw * invest)
        o = c["o"]
        grp = ptab.get(o.get("group"))
        rows.append({
            "symbol": o["symbol"], "name": o["name"], "weightPct": round(w * 100, 1),
            "score": o["score"], "pBeat10d": c["p10"], "confidence": o["confidence"], "risk": o["risk"],
            "expMedianRel10d": grp["median"] if grp else None,
            "expRange10d": [grp["q25"], grp["q75"]] if grp else None,
            "annVolPct": round(c["vol"] * 100, 1),
            "whyThisSector": o.get("evidence", []),
            "whyThisSize": "conviction (score−50)/50 × conf = %.2f, ÷ ann vol %.0f%% → share of the %.0f%% "
                           "invested budget, capped at %.0f%%"
                           % (c["conviction"], c["vol"] * 100, invest * 100, ALLOC_MAX_POS * 100),
            "against": o.get("conflicts", []),
            "wouldChange": ["composite < 50 (now %s)" % o["score"],
                            "RS group drops out of %s" % (o.get("group") or "?"),
                            "regime leaves %s (invested budget would move to %s)" %
                            (primary, {k: "%d%%" % (v * 100) for k, v in ALLOC_REGIME_INVEST.items()})],
        })
    rows.sort(key=lambda r: -r["weightPct"])
    invested = sum(r["weightPct"] for r in rows)
    # log today's published predictions for ALL sectors (calibration matures on these)
    _pred_log([{"symbol": o["symbol"], "score": o["score"], "pBeat10d": o.get("pBeat10d"),
                "confidence": o.get("confidence")} for o in opps.get("rows", [])], ptab)
    # portfolio-level factor exposures of the SUGGESTED book
    betas = _factor_betas()
    expo = {}
    for r in rows:
        for f, b in (betas.get(r["symbol"]) or {}).items():
            expo[f] = expo.get(f, 0) + r["weightPct"] / 100 * b
    exposures = sorted(({"factor": f, "exposure": round(v, 2),
                         "warn": abs(v) >= 0.35} for f, v in expo.items()),
                       key=lambda x: -abs(x["exposure"]))
    return {"regime": reg["current"]["label"], "investedPct": round(invested, 1),
            "cashPct": round(100 - invested, 1),
            "investedBudgetPct": round(invest * 100), "rows": rows, "excluded": excluded,
            "factorExposures": exposures,
            "notes": ["Suggested FRAMEWORK, not advice: conviction/vol weighting of sectors that pass "
                      "score≥55, P>50%, risk<70; invested budget set by regime (heuristic table, shown).",
                      "Expected 10d numbers are historical base-rate medians/quartiles from the probability "
                      "engine, not forecasts.",
                      "Factor exposures = Σ weight × univariate 63d beta (overlapping factors — approximate)."]}


# ── Position sizing — multiple methodologies, none crowned ───────────────────
SIZING_METHODS_DOC = {
    "fixedRisk": {"pros": "simple, uniform loss per stop-out", "cons": "ignores volatility clustering; stop distance drives share count"},
    "atrRisk": {"pros": "adapts to current volatility", "cons": "ATR lags regime shifts; assumes stop honored at 2×ATR"},
    "volTarget": {"pros": "stabilizes portfolio variance", "cons": "targets vol, not loss; leverage implied when vol is low"},
    "kellyQuarter": {"pros": "growth-optimal direction, ¼ fraction damps estimate error", "cons": "inputs are 2yr base rates — full Kelly on noisy inputs overbets catastrophically"},
    "equalRisk": {"pros": "no single position dominates portfolio risk", "cons": "ignores conviction differences entirely"},
}


def sizing_view(sym, equity, risk_pct):
    a = analyze(sym)
    vol = _sector_vol(sym)
    px = _live_px(sym)
    if not a.get("ok") or not px or not vol:
        return {"error": "no data for %s yet" % sym}
    risk_dollars = equity * risk_pct / 100
    out = {"symbol": sym, "price": round(px, 2), "equity": equity, "riskPctPerTrade": risk_pct,
           "annVolPct": round(vol * 100, 1), "methods": {}, "doc": SIZING_METHODS_DOC}
    stop = a.get("stop")
    if stop and a.get("entry") and abs(a["entry"] - stop) > 0:
        dist = abs(a["entry"] - stop)
        sh = int(risk_dollars / dist)
        out["methods"]["fixedRisk"] = {"shares": sh, "positionPct": round(sh * px / equity * 100, 1),
                                       "detail": "risk $%.0f ÷ entry-to-stop %.2f (scanner's ATR-buffered structure stop)" % (risk_dollars, dist)}
    av = a.get("atr")
    if av:
        sh = int(risk_dollars / (2 * av))
        out["methods"]["atrRisk"] = {"shares": sh, "positionPct": round(sh * px / equity * 100, 1),
                                     "detail": "risk $%.0f ÷ 2×ATR(14) %.2f" % (risk_dollars, 2 * av)}
    target_vol = 0.15
    w = min(1.0, target_vol / vol)
    out["methods"]["volTarget"] = {"shares": int(equity * w / px), "positionPct": round(w * 100, 1),
                                   "detail": "15%% ann-vol target ÷ %.0f%% sector vol → %.0f%% of equity (single-position view)" % (vol * 100, w * 100)}
    prob = cache_get("probs", 600) or _cache_and_return("probs", probabilities_view)
    grp = (prob.get("currentGroup") or {}).get(sym)
    row = next((r["horizons"].get("10") for r in prob.get("table", []) if r["group"] == grp), None)
    if row and row.get("avgWin") and row.get("avgLoss"):
        p = row["p"] / 100
        b = abs(row["avgWin"] / row["avgLoss"]) if row["avgLoss"] else None
        if b:
            f = max(0.0, (p - (1 - p) / b)) / 4
            out["methods"]["kellyQuarter"] = {"shares": int(equity * f / px), "positionPct": round(f * 100, 1),
                                              "detail": "¼-Kelly: p=%.2f, payoff=%.2f (from %s 10d base rates, n=%d) → f*=%.1f%%"
                                                        % (p, b, grp, row["n"], f * 100)}
    with _state_lock:
        n_open = len(_state["positions"])
    if n_open:
        out["methods"]["equalRisk"] = {"shares": int(risk_dollars / (vol / (252 ** 0.5) * px) / max(1, n_open + 1)),
                                       "positionPct": None,
                                       "detail": "equalize daily-vol contribution across %d existing + this position" % n_open}
    out["portfolioHeatNote"] = ("With %d open positions at %.1f%% risk each, adding this makes total heat %.1f%% "
                                "of equity — many desks cap heat at 6%%." % (n_open, risk_pct, (n_open + 1) * risk_pct))
    out["note"] = "Multiple methods on purpose — none is universally superior; the doc lists each method's failure mode."
    return out


# ── Scenario simulator & stress tests (linear factor-beta approximation) ─────
STRESS_SCENARIOS = {
    "rate_spike": {"desc": "Rapid rate rise (long-end +~50bp)", "shocks": {"TLT": -6}},
    "vol_spike": {"desc": "VIX toward 30", "shocks": {"VIXY": 40, "HYG": -3}},
    "oil_shock": {"desc": "Oil supply shock", "shocks": {"USO": 15}},
    "oil_collapse": {"desc": "Oil demand collapse", "shocks": {"USO": -20, "HYG": -4}},
    "dollar_spike": {"desc": "Dollar spike", "shocks": {"UUP": 4}},
    "tech_correction": {"desc": "Mega-cap tech correction", "shocks": {"QQQvSPY": -6}},
    "credit_stress": {"desc": "Credit stress", "shocks": {"HYG": -6, "VIXY": 30, "TLT": 3}},
    "covid_style": {"desc": "COVID-style shock (vol +150%, credit −12%, oil −30%, flight to Treasuries)",
                    "shocks": {"VIXY": 150, "HYG": -12, "USO": -30, "TLT": 8}},
}


def simulate_view(weights=None, scenario=None):
    """weights: {sym: pct} — defaults to current open positions' gross weights."""
    if not weights:
        pv = positions_view()
        tot = pv.get("totalValue") or 0
        weights = {}
        for p in pv.get("open", []):
            if p.get("last") and tot:
                weights[p["symbol"]] = weights.get(p["symbol"], 0) + \
                    p["last"] * (p.get("qty") or 1) / tot * 100 * (1 if p["dir"] == "long" else -1)
        if not weights:
            return {"error": "no positions and no weights given — pass ?w=XLK:20,XLF:10"}
    betas = _factor_betas()
    scen_names = [scenario] if scenario and scenario in STRESS_SCENARIOS else list(STRESS_SCENARIOS)
    results = []
    for name in scen_names:
        sc = STRESS_SCENARIOS[name]
        per = []
        for sym, wpct in weights.items():
            b = betas.get(sym) or {}
            impact = sum(b.get(f, 0) * shock for f, shock in sc["shocks"].items())
            per.append({"symbol": sym, "weightPct": round(wpct, 1), "impactPct": round(impact, 2),
                        "contribPct": round(impact * wpct / 100, 2)})
        per.sort(key=lambda x: x["contribPct"])
        total = round(sum(x["contribPct"] for x in per), 2)
        results.append({"scenario": name, "desc": sc["desc"], "shocks": sc["shocks"],
                        "portfolioImpactPct": total,
                        "mostVulnerable": per[:2], "mostResilient": per[-2:][::-1], "positions": per})
    results.sort(key=lambda r: r["portfolioImpactPct"])
    # simple portfolio stats for the given weights
    stats = {}
    syms = [s for s in weights if get_bars(s)]
    if syms:
        rets = {}
        mlen = 10 ** 9
        for s in syms:
            c = [b["c"] for b in get_bars(s)][-253:]
            rets[s] = [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
            mlen = min(mlen, len(rets[s]))
        port = [sum(weights[s] / 100 * rets[s][-mlen:][i] for s in syms) for i in range(mlen)]
        sd = _stdev(port)
        spyc = [b["c"] for b in (get_bars(BENCH) or [])][-(mlen + 1):]
        if len(spyc) > mlen:
            spyr = [spyc[i] / spyc[i - 1] - 1 for i in range(1, len(spyc))]
            vs = _stdev(spyr)
            cv = sum((a - sum(port) / mlen) * (b2 - sum(spyr) / mlen) for a, b2 in zip(port, spyr)) / mlen
            stats["beta"] = round(cv / (vs * vs), 2) if vs > 0 else None
        stats["annVolPct"] = round(sd * (252 ** 0.5) * 100, 1)
        eq = peak = mdd = 0.0
        for r in port:
            eq += r
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        stats["maxDD1yPct"] = round(mdd * 100, 1)
        stats["worstDayPct"] = round(min(port) * 100, 2)
    return {"weights": {k: round(v, 1) for k, v in weights.items()}, "portfolio": stats,
            "scenarios": results,
            "note": "Linear approximation: impact = Σ weight × 63d univariate factor beta × shock. Real "
                    "shocks are non-linear and correlations spike in crises — treat as direction and rough "
                    "magnitude, not precision. Portfolio stats replay the last ~252 sessions of this weight mix."}


# ── Prediction log + confidence calibration (matures on live data) ───────────
PRED_PATH = os.path.join(os.environ.get("QUANTA_DATA", "") or
                         os.path.dirname(os.path.abspath(__file__)), "predictions_history.json")
_pred_lock = threading.Lock()


def _pred_log(rows, group_probs):
    day = dt.date.today().isoformat()
    try:
        with _pred_lock:
            try:
                with open(PRED_PATH) as f:
                    hist = json.load(f)
            except (FileNotFoundError, ValueError):
                hist = {}
            if day not in hist:
                hist[day] = {r["symbol"]: {"score": r["score"], "p10": r.get("pBeat10d"),
                                           "conf": r.get("confidence")} for r in rows}
                for d in sorted(hist)[:-250]:
                    del hist[d]
                os.makedirs(os.path.dirname(PRED_PATH) or ".", exist_ok=True)
                with open(PRED_PATH + ".tmp", "w") as f:
                    json.dump(hist, f)
                os.replace(PRED_PATH + ".tmp", PRED_PATH)
    except OSError:
        pass


def calibration_view():
    m = _sector_matrix()
    with _pred_lock:
        try:
            with open(PRED_PATH) as f:
                hist = json.load(f)
        except (FileNotFoundError, ValueError):
            hist = {}
    if not m or not hist:
        return {"maturedN": 0, "days": len(hist),
                "note": "Prediction log started %s — daily P(beat SPY 10d) and scores are recorded; "
                        "calibration matures once predictions are ≥10 trading days old."
                        % (min(hist) if hist else "today")}
    dates = m["dates"]
    didx = {d.isoformat(): i for i, d in enumerate(dates)}
    buckets = {}
    matured = 0
    weekly_review = []
    for day, preds in sorted(hist.items()):
        i = didx.get(day)
        if i is None or i + 10 >= len(dates):
            continue
        day_rows = []
        for sym, pr in preds.items():
            out = _fwd_rel(m, sym, i, 10)
            if out is None or pr.get("p10") is None:
                continue
            matured += 1
            bk = "%d-%d%%" % (int(pr["p10"] // 5) * 5, int(pr["p10"] // 5) * 5 + 5)
            b = buckets.setdefault(bk, {"n": 0, "hits": 0, "pSum": 0.0})
            b["n"] += 1
            b["hits"] += 1 if out > 0 else 0
            b["pSum"] += pr["p10"]
            day_rows.append((sym, pr["score"], out))
        if day_rows:
            day_rows.sort(key=lambda x: -x[1])
            top3 = day_rows[:3]
            weekly_review.append({"date": day,
                                  "top3": [{"symbol": s, "score": sc_, "rel10d": round(o, 2)} for s, sc_, o in top3],
                                  "top3HitRate": round(100 * sum(1 for _s, _sc, o in top3 if o > 0) / len(top3))})
    rel = [{"bucket": k, "predicted": round(v["pSum"] / v["n"], 1), "realized": round(100 * v["hits"] / v["n"], 1),
            "n": v["n"]} for k, v in sorted(buckets.items())]
    return {"maturedN": matured, "days": len(hist), "reliability": rel,
            "weeklyReview": weekly_review[-8:],
            "calibrated": None if matured < 30 else all(abs(r["predicted"] - r["realized"]) <= 15 for r in rel if r["n"] >= 10),
            "note": "Live out-of-sample calibration: each day's published P(beat SPY 10d) vs what happened. "
                    "n=%d matured predictions (need ≥30 for a first read; recalibration only on evidence). "
                    "Weekly review = did that day's top-3 scores outperform over the next 10 sessions." % matured}


# ─────────────────────────────────────────────────────────────────────────────
# Market summary — synthesizes scores + rotation + breadth + options + macro
# into prose where EVERY sentence carries its numbers. Deterministic rule-based
# generator by default; if ANTHROPIC_API_KEY is set, the same data bundle is
# sent to Claude with strict grounding instructions (falls back on any error).
# ─────────────────────────────────────────────────────────────────────────────
def _summary_bundle():
    sc = cache_get("scores", 120) or _cache_and_return("scores", sector_scores)
    rot = cache_get("sectors", 120) or _cache_and_return("sectors", rotation)
    mac = macro_view()
    opts = {s: {k: (get_options(s) or {}).get(k) for k in
                ("pcrOI", "netGEX", "ivRank", "expMovePct", "skew25d")}
            for s in OPTIONS_UNIVERSE if get_options(s) and not (get_options(s) or {}).get("error")}
    return sc, rot, mac, opts


def _rule_based_summary(sc, rot, mac, opts):
    secs = sc.get("sectors") or []
    if len(secs) < 6:
        return {"text": "Not enough sector data yet — bars are still warming.", "engine": "rules"}
    lines = []
    top, bot = secs[:3], secs[-3:]
    lines.append("STRENGTH — %s lead the composite: %s. Weakest: %s."
                 % (", ".join(s["symbol"] for s in top),
                    "; ".join("%s %s (bull %s/bear %s, conf %s%%)" %
                              (s["symbol"], s["total"], s["bull"], s["bear"], s["confidence"]) for s in top),
                    "; ".join("%s %s" % (s["symbol"], s["total"]) for s in bot)))
    b = rot.get("breadth") or {}
    if b.get("n"):
        ew = b.get("ewMinusSpy1m")
        lines.append("BREADTH — %d/%d sectors above the 50-day, %d/%d above the 200-day; "
                     "equal-weight minus SPY over 1m is %+.2f%%, so leadership is %s."
                     % (b["above50"], b["n"], b["above200"], b["n"], ew or 0,
                        "broadening" if (ew or 0) >= 0 else "narrowing"))
    conf_opts, conflict = [], []
    for s in secs[:4] + secs[-2:]:
        o = opts.get(s["symbol"])
        if not o or o.get("pcrOI") is None:
            continue
        bullish_px = s["total"] >= 55
        bullish_opt = o["pcrOI"] < 0.95
        (conf_opts if bullish_px == bullish_opt else conflict).append(
            "%s (score %s vs P/C OI %.2f, GEX %+.0fM$)" % (s["symbol"], s["total"], o["pcrOI"], o.get("netGEX") or 0))
    if conf_opts or conflict:
        lines.append("OPTIONS — positioning agrees with price for %s%s."
                     % (", ".join(conf_opts) or "none",
                        ("; conflicts: " + ", ".join(conflict)) if conflict else ""))
    else:
        lines.append("OPTIONS — chain data not loaded yet (CBOE delayed feed warms within ~1 min of start).")
    reg = (mac or {}).get("regime")
    if reg:
        drivers = [r for r in mac["proxies"] if not r.get("warming") and abs(r.get("r1m") or 0) >= 2]
        lines.append("MACRO — %s. Notable 1m proxy moves: %s."
                     % (reg["read"], "; ".join("%s %+.1f%%" % (r["symbol"], r["r1m"]) for r in drivers[:4]) or "none ≥2%"))
    risks = []
    if (b.get("ewMinusSpy1m") or 0) < -1:
        risks.append("narrow leadership (EW−SPY %.1f%%)" % b["ewMinusSpy1m"])
    vix = next((r for r in (mac or {}).get("proxies", []) if r["symbol"] == "VIXY" and not r.get("warming")), None)
    if vix and (vix.get("r1m") or 0) > 5:
        risks.append("vol regime rising (VIXY +%.1f%% 1m)" % vix["r1m"])
    hi_risk = [s for s in secs[:3] if s.get("risk", 0) >= 60]
    if hi_risk:
        risks.append("leaders carry elevated risk scores (%s)" %
                     ", ".join("%s %s" % (s["symbol"], s["risk"]) for s in hi_risk))
    negg = [s for s in OPTIONS_UNIVERSE if opts.get(s, {}).get("netGEX") is not None and opts[s]["netGEX"] < 0]
    if negg:
        risks.append("negative net GEX (dealer-hedging amplification, naive convention) in " + ", ".join(negg[:4]))
    lines.append("RISKS — " + ("; ".join(risks) if risks else
                               "no acute flags from breadth, vol regime, or options positioning right now") + ".")
    # invalidation: concrete, checkable triggers with current readings
    inval = []
    if b.get("ewMinusSpy1m") is not None:
        inval.append("EW−SPY 1m crossing %s zero (now %+.2f%%) would flip the breadth read"
                     % ("above" if b["ewMinusSpy1m"] < 0 else "below", b["ewMinusSpy1m"]))
    if len(secs) >= 2:
        margin = secs[0]["total"] - secs[1]["total"]
        inval.append("%s losing the top slot needs only a %.1f-pt score swing vs %s"
                     % (secs[0]["symbol"], margin, secs[1]["symbol"]))
    spy_gex = opts.get(BENCH, {}).get("netGEX")
    if spy_gex is not None:
        inval.append("SPY net GEX flipping sign (now %+.0fM$, naive conv.) would change the vol-behavior regime" % spy_gex)
    reg2 = (mac or {}).get("regime")
    if reg2 and reg2.get("cycMinusDef1m") is not None:
        inval.append("cyclical-defensive 1m spread crossing zero (now %+.2f%%)" % reg2["cycMinusDef1m"])
    if inval:
        lines.append("INVALIDATION — watch for: " + "; ".join(inval) + ".")
    # watch today: biggest score movers + calendar
    movers = sorted([s for s in secs if s.get("delta1d") is not None], key=lambda s: -abs(s["delta1d"]))[:3]
    watch = []
    if movers and any(abs(s["delta1d"]) >= 1 for s in movers):
        watch.append("largest score moves d/d: " +
                     ", ".join("%s %+.1f" % (s["symbol"], s["delta1d"]) for s in movers))
    cal = cache_get("calendar", 1e9) or {}
    now_iso = dt.datetime.now().isoformat()
    nxt = next((e for e in (cal.get("economic") or [])
                if e.get("impact") == "High" and (e.get("time") or "") > now_iso), None)
    if nxt:
        watch.append("next high-impact release: %s %s at %s (fcst %s, prev %s)"
                     % (nxt.get("country"), nxt.get("event"), nxt.get("time", "")[11:16],
                        nxt.get("estimate") or "—", nxt.get("prev") or "—"))
    if watch:
        lines.append("WATCH TODAY — " + "; ".join(watch) + ".")
    # missing data, stated plainly
    miss = []
    ivd = min((opts[s].get("ivRank") is None for s in opts), default=True)
    hist_days = max((get_options(s) or {}).get("ivHistDays") or 0 for s in OPTIONS_UNIVERSE) if opts else 0
    if ivd:
        miss.append("IV rank / P/C z-scores still calibrating (%d/20 daily snapshots)" % hist_days)
    miss.append("options & macro score categories are unvalidated (no history for the IC test yet)")
    miss.append("ETF flows, dealer inventory, vanna/charm: not derivable from free feeds")
    lines.append("MISSING — " + "; ".join(miss) + ".")
    return {"text": "\n\n".join(lines), "engine": "rules",
            "disclaimer": "Deterministic synthesis of the numbers shown elsewhere in this dashboard; not advice."}


def _claude_summary(sc, rot, mac, opts):
    key = _key("anthropic")
    if not key:
        return None
    compact = {"scores": [{k: s[k] for k in ("symbol", "total", "bull", "bear", "confidence", "risk", "quadrant")}
                          for s in sc.get("sectors", [])],
               "breadth": rot.get("breadth"), "regime": (mac or {}).get("regime"),
               "macro": [{k: p.get(k) for k in ("symbol", "r1m", "r3m", "note")}
                         for p in (mac or {}).get("proxies", []) if not p.get("warming")],
               "options": opts}
    body = json.dumps({
        "model": "claude-sonnet-4-6", "max_tokens": 900,
        "system": "You are a sell-side market strategist. Write a concise sector-rotation brief from the JSON. "
                  "HARD RULES: every claim must cite specific numbers from the data; never invent data; if a field "
                  "is null/missing say it is unavailable; sections: STRENGTH, BREADTH, OPTIONS, MACRO, RISKS; "
                  "plain text, no markdown headers beyond the section words.",
        "messages": [{"role": "user", "content": json.dumps(compact)}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"Content-Type": "application/json", "x-api-key": key,
                                          "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        d = json.loads(resp.read().decode())
    return {"text": d["content"][0]["text"], "engine": "claude",
            "disclaimer": "AI synthesis of dashboard data (grounding-checked prompt); not advice."}


def market_summary():
    sc, rot, mac, opts = _summary_bundle()
    try:
        ai = _claude_summary(sc, rot, mac, opts)
        if ai:
            return ai
    except Exception as e:
        print("warn: claude summary failed (%s) — using rule-based" % e)
    return _rule_based_summary(sc, rot, mac, opts)


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
    # anchored VWAP from the last confirmed swing pivot (the institutional
    # "who's underwater since the turn" line); falls back to window start
    anchor = pivots[-1][0] if pivots else offset
    avwap = [None] * len(show)
    cpv = cv = 0.0
    for i in range(anchor, len(bars)):
        b = bars[i]
        cpv += (b["h"] + b["l"] + b["c"]) / 3 * b.get("v", 0)
        cv += b.get("v", 0)
        if i >= offset and cv:
            avwap[i - offset] = round(cpv / cv, 2)
    return {"symbol": symbol, "tf": tf, "ok": a.get("ok", False), "setup": a,
            "bars": show, "sma20": sma_series(20), "sma50": sma_series(50), "pivots": pv,
            "avwap": avwap,
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
# Options intelligence — CBOE delayed chains (keyless, ~15-min delayed).
# The feed provides per-contract greeks (delta/gamma/vega/theta), IV, OI and
# volume, so everything below is CALCULATED from quoted data, never estimated:
#   GEX / DEX / vega exposure, call & put walls, gamma flip (strike-profile
#   approximation), max pain, put/call ratios, expected move (ATM straddle),
#   ATM IV + 25Δ skew + term structure, volume/OI, unusual activity.
# GEX sign uses the standard naive dealer convention (+calls / −puts) — actual
# dealer inventory is NOT observable; the UI says so. IV rank/percentile and
# OI change need history, so daily snapshots accumulate in options_history.json
# and those metrics switch on once enough days exist. NOT derivable from this
# feed (shown as unavailable): vanna, charm, true dealer positioning, block
# trades, ETF flows.
# ─────────────────────────────────────────────────────────────────────────────
OPTIONS_UNIVERSE = [s for s, _ in SECTORS] + [BENCH]
OPTIONS_UNAVAILABLE = ["vanna", "charm", "true dealer positioning (GEX shown with naive +call/−put convention)",
                       "block trades", "ETF fund flows"]
_options_lock, _options = threading.Lock(), {}
OPT_HISTORY_DAYS_MIN = 20


def _parse_occ(code):
    """OCC code like XLK260918C00149000 -> (expiry_date, 'C'|'P', strike)."""
    strike = int(code[-8:]) / 1000.0
    cp = code[-9]
    d = code[-15:-9]
    exp = dt.date(2000 + int(d[:2]), int(d[2:4]), int(d[4:6]))
    return exp, cp, strike


def fetch_options_summary(symbol):
    raw = http_get_json("https://cdn.cboe.com/api/global/delayed_quotes/options/%s.json"
                        % urllib.parse.quote(symbol), timeout=25)
    data = raw.get("data") or {}
    spot = data.get("current_price") or data.get("close")
    chain = data.get("options") or []
    if not spot or not chain:
        raise ValueError("empty chain for %s" % symbol)
    today = dt.date.today()
    con = []
    for o in chain:
        try:
            exp, cp, strike = _parse_occ(o["option"])
        except (KeyError, ValueError, IndexError):
            continue
        dte = (exp - today).days
        if dte < 0 or dte > 90:
            continue
        con.append({"exp": exp, "dte": dte, "cp": cp, "k": strike,
                    "oi": o.get("open_interest") or 0, "vol": o.get("volume") or 0,
                    "iv": o.get("iv") or 0, "delta": o.get("delta") or 0,
                    "gamma": o.get("gamma") or 0, "vega": o.get("vega") or 0,
                    "bid": o.get("bid") or 0, "ask": o.get("ask") or 0})
    if not con:
        raise ValueError("no <=90d contracts for %s" % symbol)

    # exposures (per 1% move for GEX; naive dealer sign: +calls / −puts)
    gex = dex = vega_exp = 0.0
    call_oi = put_oi = call_vol = put_vol = 0.0
    by_strike = {}
    for c in con:
        g = c["gamma"] * c["oi"] * 100 * spot * spot * 0.01
        gex += g if c["cp"] == "C" else -g
        dex += c["delta"] * c["oi"] * 100 * spot
        vega_exp += c["vega"] * c["oi"] * 100
        s = by_strike.setdefault(c["k"], {"gex": 0.0, "coi": 0, "poi": 0})
        s["gex"] += g if c["cp"] == "C" else -g
        if c["cp"] == "C":
            call_oi += c["oi"]; call_vol += c["vol"]; s["coi"] += c["oi"]
        else:
            put_oi += c["oi"]; put_vol += c["vol"]; s["poi"] += c["oi"]

    # gamma flip: recompute net GEX with Black-Scholes gamma re-evaluated at
    # shifted spot levels (r=0, quoted IV per contract) — the proper definition,
    # not the cumulative-by-strike shortcut. Also yields the GEX(S) curve.
    def _bs_gamma(S, K, iv, T):
        if iv <= 0 or T <= 0 or S <= 0 or K <= 0:
            return 0.0
        st = iv * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * iv * iv * T) / st
        return math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi) / (S * st)

    live_con = [c for c in con if c["oi"] > 0 and c["iv"] > 0 and c["dte"] >= 1]
    gex_curve = []
    for step_i in range(-10, 11):
        S = spot * (1 + step_i * 0.015)
        net = sum((1 if c["cp"] == "C" else -1) * _bs_gamma(S, c["k"], c["iv"], c["dte"] / 365.0)
                  * c["oi"] * 100 * S * S * 0.01 for c in live_con)
        gex_curve.append({"s": round(S, 2), "gex": round(net / 1e6, 1)})
    flip = None
    for i in range(1, len(gex_curve)):
        a, b2 = gex_curve[i - 1], gex_curve[i]
        if (a["gex"] < 0) != (b2["gex"] < 0) and b2["gex"] != a["gex"]:
            x = a["s"] + (b2["s"] - a["s"]) * (-a["gex"]) / (b2["gex"] - a["gex"])
            if flip is None or abs(x - spot) < abs(flip - spot):
                flip = x
    ks = sorted(by_strike)

    near = [k for k in ks if 0.8 * spot <= k <= 1.2 * spot]
    call_wall = max(near, key=lambda k: by_strike[k]["coi"], default=None)
    put_wall = max(near, key=lambda k: by_strike[k]["poi"], default=None)

    # front expiry (nearest with >=1 DTE): max pain, expected move, ATM IV, skew
    front = min((c["exp"] for c in con if c["dte"] >= 1), default=None)
    fcon = [c for c in con if c["exp"] == front]
    max_pain = exp_move = atm_iv = skew = None
    fdte = None
    if fcon:
        fdte = fcon[0]["dte"]
        fks = sorted(set(c["k"] for c in fcon))
        def payout(kx):
            tot = 0.0
            for c in fcon:
                if c["cp"] == "C" and kx > c["k"]:
                    tot += (kx - c["k"]) * c["oi"]
                elif c["cp"] == "P" and kx < c["k"]:
                    tot += (c["k"] - kx) * c["oi"]
            return tot
        max_pain = min(fks, key=payout) if fks else None
        atm_k = min(fks, key=lambda k: abs(k - spot)) if fks else None
        if atm_k is not None:
            ac = next((c for c in fcon if c["k"] == atm_k and c["cp"] == "C"), None)
            ap = next((c for c in fcon if c["k"] == atm_k and c["cp"] == "P"), None)
            if ac and ap:
                mid = lambda c: (c["bid"] + c["ask"]) / 2 if (c["bid"] and c["ask"]) else 0
                straddle = mid(ac) + mid(ap)
                exp_move = round(straddle / spot * 100, 2) if straddle else None
                ivs = [c["iv"] for c in (ac, ap) if c["iv"]]
                atm_iv = round(sum(ivs) / len(ivs) * 100, 1) if ivs else None
        p25 = min((c for c in fcon if c["cp"] == "P" and c["iv"]),
                  key=lambda c: abs(c["delta"] + 0.25), default=None)
        c25 = min((c for c in fcon if c["cp"] == "C" and c["iv"]),
                  key=lambda c: abs(c["delta"] - 0.25), default=None)
        if p25 and c25 and abs(p25["delta"] + 0.25) < 0.12 and abs(c25["delta"] - 0.25) < 0.12:
            skew = round((p25["iv"] - c25["iv"]) * 100, 1)

    # term structure: ATM IV of the first 6 expiries
    term = []
    for e in sorted(set(c["exp"] for c in con))[:6]:
        ec = [c for c in con if c["exp"] == e and c["iv"]]
        if not ec:
            continue
        kk = min(set(c["k"] for c in ec), key=lambda k: abs(k - spot))
        ivs = [c["iv"] for c in ec if c["k"] == kk]
        term.append({"exp": e.isoformat(), "dte": (e - today).days,
                     "atmIV": round(sum(ivs) / len(ivs) * 100, 1)})

    unusual = sorted([c for c in con if c["vol"] >= 300 and c["vol"] >= 2 * max(c["oi"], 1)],
                     key=lambda c: c["vol"], reverse=True)[:5]

    return {
        "symbol": symbol, "spot": spot, "updated": time.time(), "source": "cboe-delayed",
        "iv30": data.get("iv30"), "contracts": len(con), "windowDays": 90,
        "netGEX": round(gex / 1e6, 1), "netDEX": round(dex / 1e6, 1),          # $M
        "vegaExp": round(vega_exp / 1e6, 2),                                    # $M per IV pt
        "gammaFlip": round(flip, 2) if flip else None, "gexCurve": gex_curve,
        "callWall": call_wall, "putWall": put_wall, "maxPain": max_pain,
        "pcrOI": round(put_oi / call_oi, 2) if call_oi else None,
        "pcrVol": round(put_vol / call_vol, 2) if call_vol else None,
        "totalOI": int(call_oi + put_oi), "totalVol": int(call_vol + put_vol),
        "volOverOI": round((call_vol + put_vol) / (call_oi + put_oi), 3) if (call_oi + put_oi) else None,
        "expMovePct": exp_move, "expMoveDTE": fdte, "atmIV": atm_iv, "skew25d": skew,
        "term": term,
        "unusual": [{"cp": c["cp"], "k": c["k"], "exp": c["exp"].isoformat(),
                     "vol": int(c["vol"]), "oi": int(c["oi"]),
                     "iv": round(c["iv"] * 100, 1) if c["iv"] else None} for c in unusual],
        "profile": [{"k": k, "gex": round(by_strike[k]["gex"] / 1e6, 2),
                     "coi": int(by_strike[k]["coi"]), "poi": int(by_strike[k]["poi"])}
                    for k in near],
        "unavailable": OPTIONS_UNAVAILABLE,
    }


# ── daily history (IV rank / OI change switch on as snapshots accumulate) ────
OPT_HIST_PATH = os.path.join(os.environ.get("QUANTA_DATA", "") or
                             os.path.dirname(os.path.abspath(__file__)), "options_history.json")
_opt_hist_lock = threading.Lock()


def _opt_history_update(summ):
    day = dt.date.today().isoformat()
    try:
        with _opt_hist_lock:
            try:
                with open(OPT_HIST_PATH) as f:
                    hist = json.load(f)
            except (FileNotFoundError, ValueError):
                hist = {}
            h = hist.setdefault(summ["symbol"], {})
            # gex/dex stored so positioning-CHANGE research activates as days accrue
            h[day] = {"iv30": summ.get("iv30"), "oi": summ.get("totalOI"), "pcr": summ.get("pcrOI"),
                      "gex": summ.get("netGEX"), "dex": summ.get("netDEX")}
            for d in sorted(h)[:-260]:      # keep ~1yr
                del h[d]
            os.makedirs(os.path.dirname(OPT_HIST_PATH) or ".", exist_ok=True)
            with open(OPT_HIST_PATH + ".tmp", "w") as f:
                json.dump(hist, f)
            os.replace(OPT_HIST_PATH + ".tmp", OPT_HIST_PATH)
    except OSError:
        return {}
    return hist.get(summ["symbol"], {})


def _opt_enrich_from_history(summ, h):
    days = sorted(h)
    ivs = [h[d]["iv30"] for d in days if h[d].get("iv30")]
    summ["ivHistDays"] = len(ivs)
    # P/C ratio z-score vs this symbol's OWN history — absolute PCR levels are
    # structural (index/hedged products sit far above 1.0), so only deviation
    # from the symbol's norm is information.
    pcrs = [h[d]["pcr"] for d in days if h[d].get("pcr")]
    if len(pcrs) >= OPT_HISTORY_DAYS_MIN and summ.get("pcrOI"):
        mu, sd = sum(pcrs) / len(pcrs), _stdev(pcrs)
        summ["pcrZ"] = round((summ["pcrOI"] - mu) / sd, 2) if sd > 0.01 else 0.0
    else:
        summ["pcrZ"] = None
    if len(ivs) >= OPT_HISTORY_DAYS_MIN and summ.get("iv30"):
        lo, hi = min(ivs), max(ivs)
        summ["ivRank"] = round((summ["iv30"] - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0
        summ["ivPctile"] = round(100 * sum(1 for v in ivs if v <= summ["iv30"]) / len(ivs), 1)
    else:
        summ["ivRank"] = summ["ivPctile"] = None   # needs >=20 daily snapshots
    prev = [d for d in days if d < dt.date.today().isoformat()]
    if prev and h[prev[-1]].get("oi") and summ.get("totalOI"):
        summ["oiChange"] = summ["totalOI"] - h[prev[-1]]["oi"]
        summ["oiChangePct"] = round((summ["totalOI"] / h[prev[-1]]["oi"] - 1) * 100, 1)
    else:
        summ["oiChange"] = summ["oiChangePct"] = None
    summ["gexChange"] = (round(summ["netGEX"] - h[prev[-1]]["gex"], 1)
                         if prev and h[prev[-1]].get("gex") is not None and summ.get("netGEX") is not None
                         else None)
    return summ


def get_options(symbol):
    with _options_lock:
        return _options.get(symbol)


def options_loop():
    while True:
        for sym in OPTIONS_UNIVERSE:
            try:
                summ = fetch_options_summary(sym)
                summ = _opt_enrich_from_history(summ, _opt_history_update(summ))
                with _options_lock:
                    _options[sym] = summ
            except Exception as e:
                with _options_lock:
                    if sym not in _options:
                        _options[sym] = {"symbol": sym, "error": str(e), "source": "cboe-delayed"}
            time.sleep(3)
        time.sleep(900)


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
    ctx = {}
    try:
        m = _sector_matrix()
        reg = regime_at(m, len(m["dates"]) - 1)["primary"] if m else None
        ws = _weekly_states()
        if ws:
            last = ws["states"][-1]
            rk = last["rank"].get(sym)
            ctx = {"rsGroup": (next((g for g, lo, hi in RANK_GROUPS if lo <= rk <= hi), None)
                               if rk is not None else None),
                   "breadth": last["features"]["breadth"], "volPct": last["features"]["volPct"]}
    except Exception:
        reg = None
    p = {"id": _next_id(), "symbol": sym,
         "dir": "short" if d.get("dir") == "short" else "long",
         "qty": _fnum(d.get("qty")) or 1,
         "entry": entry, "stop": _fnum(d.get("stop")), "target": _fnum(d.get("target")),
         "note": str(d.get("note", ""))[:120], "opened": time.time(),
         # entry-context tags so the journal can learn which conditions suit YOUR
         # trading (regime, the symbol's RS group, breadth, vol percentile)
         "regime": reg, "entryCtx": ctx}
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

    # risk analytics from 63d daily returns (positions without bar history are
    # excluded and said so — no guessing betas)
    def _rets(sym, n=63):
        b = get_bars(sym)
        if not b or len(b) < n + 1:
            return None
        cc = [x["c"] for x in b][-(n + 1):]
        return [cc[i] / cc[i - 1] - 1 for i in range(1, len(cc))]

    def _cov(a, b):
        m = min(len(a), len(b))
        a, b = a[-m:], b[-m:]
        ma, mb = sum(a) / m, sum(b) / m
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / m

    analytics = {"beta": None, "expDailyVolPct": None, "avgPairCorr": None, "excluded": []}
    spy_r = _rets(BENCH)
    held = []
    for r_ in rows:
        if not (r_.get("last") and tot_val):
            continue
        rr = _rets(r_["symbol"])
        if rr is None:
            analytics["excluded"].append(r_["symbol"])
            continue
        w_ = r_["last"] * (r_.get("qty") or 1) / tot_val * (1 if r_["dir"] == "long" else -1)
        held.append((r_["symbol"], w_, rr))
    if held and spy_r:
        var_spy = _cov(spy_r, spy_r)
        if var_spy > 0:
            analytics["beta"] = round(sum(w * _cov(rr, spy_r) / var_spy for _s, w, rr in held), 2)
        pvar = sum(w1 * w2 * _cov(r1, r2) for _s1, w1, r1 in held for _s2, w2, r2 in held)
        if pvar >= 0:
            analytics["expDailyVolPct"] = round((pvar ** 0.5) * 100, 2)
        if len(held) > 1:
            cs = []
            for i in range(len(held)):
                for j in range(i + 1, len(held)):
                    v1, v2 = _cov(held[i][2], held[i][2]), _cov(held[j][2], held[j][2])
                    if v1 > 0 and v2 > 0:
                        cs.append(_cov(held[i][2], held[j][2]) / (v1 ** 0.5 * v2 ** 0.5))
            if cs:
                analytics["avgPairCorr"] = round(sum(cs) / len(cs), 2)
    # stress: replay the CURRENT allocation over the last ~250 sessions —
    # worst day, VaR95, max drawdown, annualized vol/Sharpe. This is the
    # allocation's history, NOT your trade record (it says so in the UI).
    if held:
        hrets = []
        for _s, w_, _r in held:
            rr = _rets(_s, 250)
            hrets.append((w_, rr))
        m = min(len(r) for _w, r in hrets if r)
        if m >= 60:
            port = [sum(w_ * r[-m:][i] for w_, r in hrets) for i in range(m)]
            sp = sorted(port)
            eq = peak = mdd = 0.0
            for r_ in port:
                eq += r_
                peak = max(peak, eq)
                mdd = min(mdd, eq - peak)
            mu, sd = sum(port) / m, _stdev(port)
            analytics["stress"] = {
                "days": m,
                "worstDayPct": round(sp[0] * 100, 2),
                "var95Pct": round(sp[int(m * 0.05)] * 100, 2),
                "maxDDPct": round(mdd * 100, 2),
                "annVolPct": round(sd * (252 ** 0.5) * 100, 1),
                "sharpe": round(mu / sd * (252 ** 0.5), 2) if sd > 0 else None,
                "note": "current allocation replayed over %d sessions — not your trade record" % m,
            }
    analytics["note"] = "63d daily returns; weights = share of gross exposure (shorts negative)"
    # concentration warnings — the numbers that make a portfolio one trade in disguise
    warnings = []
    for a in ({"symbol": k, "pct": round(v / tot_val * 100, 1)} for k, v in alloc.items() if tot_val):
        if a["pct"] > 40:
            warnings.append("%s is %.0f%% of gross exposure — concentration" % (a["symbol"], a["pct"]))
    if (analytics.get("avgPairCorr") or 0) > 0.75:
        warnings.append("avg pairwise correlation %.2f — positions are one trade in disguise" % analytics["avgPairCorr"])
    if analytics.get("beta") is not None and abs(analytics["beta"]) > 1.5:
        warnings.append("portfolio beta %.2f vs SPY — outsized market exposure" % analytics["beta"])
    if (analytics.get("expDailyVolPct") or 0) > 2.5:
        warnings.append("expected daily vol %.2f%% — hot sizing" % analytics["expDailyVolPct"])
    analytics["warnings"] = warnings

    # trade-journal intelligence (closed trades; small n is labeled, not hidden)
    def _jgroup(keyfn):
        g = {}
        for c in closed:
            g.setdefault(keyfn(c) or "?", []).append(c)
        out_ = []
        for k, v in g.items():
            pls = [c.get("pl") or 0 for c in v]
            holds = [(c["closedAt"] - c["opened"]) / 86400 for c in v if c.get("closedAt") and c.get("opened")]
            out_.append({"key": k, "n": len(v), "win": round(100 * sum(1 for x in pls if x > 0) / len(pls)),
                         "totalPL": round(sum(pls), 2), "avgPL": round(sum(pls) / len(pls), 2),
                         "avgHoldDays": round(sum(holds) / len(holds), 1) if holds else None})
        out_.sort(key=lambda r: -r["totalPL"])
        return out_
    journal = {"bySymbol": _jgroup(lambda c: c["symbol"]),
               "byDir": _jgroup(lambda c: c.get("dir")),
               "byRegime": _jgroup(lambda c: c.get("regime")),
               "byEntryRS": _jgroup(lambda c: (c.get("entryCtx") or {}).get("rsGroup")),
               "note": "closed trades only — groups with n<10 are anecdotes, not statistics"} if closed else None
    return {"open": rows, "closed": closed[::-1], "analytics": analytics, "journal": journal,
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
        if len(_alert_seen) > 800:      # bound the dedupe map (it grows forever otherwise)
            for k2 in sorted(_alert_seen, key=_alert_seen.get)[:200]:
                del _alert_seen[k2]
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


def _check_portfolio_risk():
    with _state_lock:
        has = bool(_state["positions"])
    if not has:
        return
    for wmsg in (positions_view().get("analytics") or {}).get("warnings", []):
        push_alert("risk", "PORTFOLIO", wmsg, "warn", dedupe_hours=24, key=wmsg[:40])


def check_alerts():
    for fn in (_check_signal_alerts, _check_setup_alerts, _check_rotation_alerts,
               _check_position_alerts, _check_price_alerts, _check_portfolio_risk):
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
        elif path == "/api/scores":
            wq = qs.get("weights", [None])[0]
            if wq:
                self._json(sector_scores(wq))       # custom weights: never cached
            else:
                self._json(cache_get("scores", 120) or _cache_and_return("scores", sector_scores))
        elif path == "/api/options":
            sym = (qs.get("symbol", [BENCH])[0]).upper()
            self._json(get_options(sym) or {"symbol": sym, "error": "options not loaded yet (feed warms ~3s/symbol)",
                                            "unavailable": OPTIONS_UNAVAILABLE})
        elif path == "/api/options_all":
            with _options_lock:
                self._json({"options": {k: {kk: v.get(kk) for kk in
                                            ("spot", "netGEX", "netDEX", "pcrOI", "pcrVol", "iv30", "ivRank",
                                             "expMovePct", "gammaFlip", "callWall", "putWall", "maxPain",
                                             "oiChangePct", "error", "updated")}
                                        for k, v in _options.items()}})
        elif path == "/api/macro":
            self._json(cache_get("macro", 300) or _cache_and_return("macro", macro_view))
        elif path == "/api/summary":
            self._json(cache_get("summary", 600) or _cache_and_return("summary", market_summary))
        elif path == "/api/regime":
            self._json(cache_get("regime", 600) or _cache_and_return("regime", regime_view))
        elif path == "/api/probabilities":
            self._json(cache_get("probs", 600) or _cache_and_return("probs", probabilities_view))
        elif path == "/api/analogs":
            self._json(cache_get("analogs", 600) or _cache_and_return("analogs", analogs_view))
        elif path == "/api/research":
            self._json(cache_get("research", 600) or _cache_and_return("research", research_view))
        elif path == "/api/opportunities":
            self._json(cache_get("opps", 300) or _cache_and_return("opps", opportunities_view))
        elif path == "/api/factors":
            self._json(cache_get("factors", 600) or _cache_and_return("factors", factors_view))
        elif path == "/api/edgelab":
            self._json(cache_get("edgelab", 900) or _cache_and_return("edgelab", edge_lab))
        elif path == "/api/registry":
            self._json(cache_get("registry", 300) or _cache_and_return("registry", registry_view))
        elif path == "/api/allocation":
            self._json(cache_get("alloc", 300) or _cache_and_return("alloc", allocation_view))
        elif path == "/api/sizing":
            sym = (qs.get("symbol", ["XLK"])[0]).upper()
            try:
                eq = float(qs.get("equity", ["100000"])[0])
                rp = float(qs.get("risk", ["1"])[0])
            except ValueError:
                self._json({"error": "bad equity/risk"}, 400)
                return
            self._json(sizing_view(sym, eq, rp))
        elif path == "/api/simulate":
            wq = qs.get("w", [None])[0]
            weights = None
            if wq:
                try:
                    weights = {p.split(":")[0].upper(): float(p.split(":")[1]) for p in wq.split(",")}
                except (ValueError, IndexError):
                    self._json({"error": "bad weights — use w=XLK:20,XLF:10"}, 400)
                    return
            self._json(simulate_view(weights, qs.get("scenario", [None])[0]))
        elif path == "/api/calibration":
            self._json(cache_get("calib", 600) or _cache_and_return("calib", calibration_view))
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
    print("  options  : CBOE delayed chains for %d symbols (greeks/OI/IV — GEX, walls, max pain…)" % len(OPTIONS_UNIVERSE))
    for fn in (quotes_loop, bars_loop, live_loop, news_loop, calendar_loop, options_loop):
        threading.Thread(target=fn, daemon=True).start()
    # Dual-stack listener: browsers resolving `localhost` often try ::1 first —
    # an IPv4-only bind costs ~2s per request on such clients (measured on
    # Windows: 2050ms via localhost vs 1ms via 127.0.0.1). Fall back to IPv4 if
    # the host has no IPv6 (e.g. some containers).
    class DualStackServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6

        def server_bind(self):
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
            ThreadingHTTPServer.server_bind(self)

    try:
        server = DualStackServer(("::", PORT), Handler)
    except OSError:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down"); server.shutdown()


if __name__ == "__main__":
    main()
