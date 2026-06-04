#!/usr/bin/env python3
"""
Quanta standalone — a zero-dependency morning-debrief trading dashboard.

A companion to your main platform (e.g. ThinkOrSwim): glanceable market context,
news, calendar, and a watchlist screener — plus an optional AI morning brief.

Runs a tiny HTTP server (Python standard library only) that serves:
  /                 the dashboard (index.html)
  /api/quotes       index / futures / macro snapshot
  /api/news         categorized + sentiment-tagged market news
  /api/calendar     economic + earnings events (best-effort, free tier)
  /api/screener     fundamentals + heuristic scores for a list of tickers
  /api/brief        morning debrief (rule-based, or AI if an Anthropic key is set)

No pip install, no database, no auth. Just:  python3 quanta.py

Keys: copy keys.local.json.example -> keys.local.json and fill it in, or set
env vars. With no key set it runs in MOCK mode so you can try it instantly.
"""

import datetime as dt
import json
import os
import random
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
def _load_local_keys():
    """Load API keys from keys.local.json next to this script, if present.
    That file is gitignored, so your keys never get committed/pushed."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.local.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


_LOCAL_KEYS = _load_local_keys()


def _key(name):
    return os.environ.get(name.upper() + "_API_KEY") or _LOCAL_KEYS.get(name, "")


# Resolution per provider: env var → keys.local.json → empty.
# Do NOT hardcode keys here — this file is committed to git.
API_KEYS = {
    "polygon": _key("polygon"),
    "finnhub": _key("finnhub"),
    "alphavantage": _key("alphavantage"),
}
PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "").lower()
PORT = int(os.environ.get("PORT", "8000"))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "20"))
# Default screener watchlist (override in the UI or via SCREENER_SYMBOLS).
SCREENER_SYMBOLS = [s.strip().upper() for s in os.environ.get(
    "SCREENER_SYMBOLS", "AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,NFLX,JPM").split(",") if s.strip()]

INSTRUMENTS = [
    ("SPY",  "S&P 500 ETF",          "etf",    {"polygon": "SPY", "finnhub": "SPY", "alphavantage": "SPY"}),
    ("QQQ",  "Nasdaq 100 ETF",       "etf",    {"polygon": "QQQ", "finnhub": "QQQ", "alphavantage": "QQQ"}),
    ("IWM",  "Russell 2000 ETF",     "etf",    {"polygon": "IWM", "finnhub": "IWM", "alphavantage": "IWM"}),
    ("DIA",  "Dow Jones ETF",        "etf",    {"polygon": "DIA", "finnhub": "DIA", "alphavantage": "DIA"}),
    ("VIX",  "Volatility Index",     "index",  {"polygon": "I:VIX", "finnhub": "^VIX", "alphavantage": "VIXY"}),
    ("ES",   "E-mini S&P 500",       "future", {"polygon": "SPY", "finnhub": "SPY", "alphavantage": "SPY"}),
    ("NQ",   "E-mini Nasdaq 100",    "future", {"polygon": "QQQ", "finnhub": "QQQ", "alphavantage": "QQQ"}),
    ("RTY",  "E-mini Russell 2000",  "future", {"polygon": "IWM", "finnhub": "IWM", "alphavantage": "IWM"}),
    ("CL",   "Crude Oil WTI",        "future", {"polygon": "USO", "finnhub": "USO", "alphavantage": "USO"}),
    ("GC",   "Gold",                 "future", {"polygon": "GLD", "finnhub": "GLD", "alphavantage": "GLD"}),
    ("US10Y","US 10Y Yield",         "rate",   {"polygon": "I:TNX", "finnhub": "^TNX", "alphavantage": "IEF"}),
    ("DXY",  "US Dollar Index",      "index",  {"polygon": "I:DXY", "finnhub": "^DXY", "alphavantage": "UUP"}),
]
SEED_PRICES = {
    "SPY": 545.0, "QQQ": 470.0, "IWM": 205.0, "DIA": 395.0, "VIX": 14.2,
    "ES": 5460.0, "NQ": 19500.0, "RTY": 2050.0, "CL": 78.5, "GC": 2350.0,
    "US10Y": 4.35, "DXY": 104.8,
}

FINNHUB = "https://finnhub.io/api/v1"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper + tiny TTL cache
# ─────────────────────────────────────────────────────────────────────────────
def http_get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "quanta-standalone"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


_cache = {}
_cache_lock = threading.Lock()


def cache_get(key, ttl):
    with _cache_lock:
        item = _cache.get(key)
    if item and (time.time() - item[0]) < ttl:
        return item[1]
    return None


def cache_set(key, value):
    with _cache_lock:
        _cache[key] = (time.time(), value)


# ─────────────────────────────────────────────────────────────────────────────
# Quote providers
# ─────────────────────────────────────────────────────────────────────────────
def active_provider():
    if PROVIDER in ("polygon", "finnhub", "alphavantage", "mock"):
        return PROVIDER
    for name in ("finnhub", "polygon", "alphavantage"):  # finnhub first: best free tier
        if API_KEYS.get(name):
            return name
    return "mock"


def quote_finnhub(sym, vendor):
    url = "%s/quote?symbol=%s&token=%s" % (FINNHUB, urllib.parse.quote(vendor),
                                           urllib.parse.quote(API_KEYS["finnhub"]))
    d = http_get_json(url)
    if not d or (d.get("c", 0) == 0 and d.get("pc", 0) == 0):
        raise ValueError("empty finnhub quote")
    return {
        "last": d.get("c", 0.0), "change": d.get("d", 0.0), "changePercent": d.get("dp", 0.0),
        "open": d.get("o", 0.0), "high": d.get("h", 0.0), "low": d.get("l", 0.0),
        "prevClose": d.get("pc", 0.0), "volume": 0, "atr": d.get("h", 0.0) - d.get("l", 0.0),
        "weekChangePct": 0.0, "relVolume": 0.0, "trendStrength": 0.0,
    }


def quote_alphavantage(sym, vendor):
    url = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=%s&apikey=%s" % (
        urllib.parse.quote(vendor), urllib.parse.quote(API_KEYS["alphavantage"]))
    d = http_get_json(url).get("Global Quote", {})
    if not d.get("05. price"):
        raise ValueError("empty/limited alphavantage quote")
    f = lambda k: float(d.get(k, 0) or 0)
    pct = d.get("10. change percent", "0").replace("%", "")
    return {
        "last": f("05. price"), "change": f("09. change"), "changePercent": float(pct or 0),
        "open": f("02. open"), "high": f("03. high"), "low": f("04. low"),
        "prevClose": f("08. previous close"), "volume": int(f("06. volume")),
        "atr": f("03. high") - f("04. low"), "weekChangePct": 0.0, "relVolume": 0.0, "trendStrength": 0.0,
    }


def quote_polygon(sym, vendor):
    key = urllib.parse.quote(API_KEYS["polygon"])
    if vendor.startswith("I:"):
        url = "https://api.polygon.io/v3/snapshot/indices?ticker=%s&apiKey=%s" % (urllib.parse.quote(vendor), key)
        res = http_get_json(url).get("results", [])
        if not res:
            raise ValueError("empty polygon index")
        r = res[0]; s = r.get("session", {})
        return {
            "last": r.get("value", 0.0), "change": s.get("change", 0.0),
            "changePercent": s.get("change_percent", 0.0), "open": s.get("open", 0.0),
            "high": s.get("high", 0.0), "low": s.get("low", 0.0),
            "prevClose": s.get("previous_close", 0.0), "volume": 0,
            "atr": s.get("high", 0.0) - s.get("low", 0.0), "weekChangePct": 0.0,
            "relVolume": 0.0, "trendStrength": 0.0,
        }
    url = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/%s?apiKey=%s" % (
        urllib.parse.quote(vendor), key)
    t = http_get_json(url).get("ticker", {})
    day, prev, lt = t.get("day", {}), t.get("prevDay", {}), t.get("lastTrade", {})
    last = lt.get("p") or day.get("c", 0.0)
    relv = (day.get("v", 0) / prev["v"]) if prev.get("v") else 0.0
    return {
        "last": last, "change": t.get("todaysChange", 0.0), "changePercent": t.get("todaysChangePerc", 0.0),
        "open": day.get("o", 0.0), "high": day.get("h", 0.0), "low": day.get("l", 0.0),
        "prevClose": prev.get("c", 0.0), "volume": int(day.get("v", 0)),
        "atr": day.get("h", 0.0) - day.get("l", 0.0), "weekChangePct": 0.0,
        "relVolume": relv, "trendStrength": 0.0,
    }


_mock_state = {}


def quote_mock(sym, vendor):
    st = _mock_state.get(sym)
    if st is None:
        base = SEED_PRICES.get(sym, 100.0)
        st = {"last": base, "prevClose": base * (1 - (random.random() - 0.5) * 0.01),
              "week": base * (1 - (random.random() - 0.5) * 0.04), "open": base,
              "high": base, "low": base, "vol": random.randint(10_000_000, 40_000_000),
              "avg": random.randint(30_000_000, 80_000_000)}
        _mock_state[sym] = st
    st["last"] = max(0.01, st["last"] + (random.random() - 0.5) * 0.001 * st["last"])
    st["high"] = max(st["high"], st["last"]); st["low"] = min(st["low"], st["last"])
    st["vol"] += random.randint(0, 250_000)
    r2 = lambda x: round(x, 2)
    return {
        "last": r2(st["last"]), "prevClose": r2(st["prevClose"]), "open": r2(st["open"]),
        "high": r2(st["high"]), "low": r2(st["low"]), "volume": st["vol"],
        "change": r2(st["last"] - st["prevClose"]),
        "changePercent": r2((st["last"] - st["prevClose"]) / st["prevClose"] * 100),
        "weekChangePct": r2((st["last"] - st["week"]) / st["week"] * 100),
        "relVolume": r2(st["vol"] / max(st["avg"], 1)), "atr": r2(st["last"] * 0.012),
        "trendStrength": r2(20 + random.random() * 60),
    }


PROVIDER_FNS = {"finnhub": quote_finnhub, "alphavantage": quote_alphavantage,
                "polygon": quote_polygon, "mock": quote_mock}

_quotes_lock = threading.Lock()
_quotes_cache = []
_status = {"provider": active_provider(), "updated": 0}


def refresh_loop():
    provider = active_provider()
    fn = PROVIDER_FNS[provider]
    while True:
        out = []
        for sym, name, klass, vendors in INSTRUMENTS:
            vendor = vendors.get(provider, sym)
            try:
                q = fn(sym, vendor); src = provider
            except Exception:
                q = quote_mock(sym, vendor); src = "mock"
            q.update({"symbol": sym, "name": name, "assetClass": klass, "source": src})
            out.append(q)
            if provider == "alphavantage":
                time.sleep(13)
        with _quotes_lock:
            global _quotes_cache
            _quotes_cache = out
            _status["updated"] = int(time.time())
        time.sleep(REFRESH_SECONDS)


# ─────────────────────────────────────────────────────────────────────────────
# News  (Finnhub /news, free) + lightweight classification
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_RULES = [
    ("Fed",        ["fed", "fomc", "powell", "rate cut", "rate hike", "interest rate", "central bank"]),
    ("Inflation",  ["cpi", "ppi", "inflation", "pce", "deflation"]),
    ("Jobs",       ["jobs", "payroll", "nfp", "unemployment", "jobless", "labor market"]),
    ("Earnings",   ["earnings", "eps", "revenue", "guidance", "beats", "misses", "quarter"]),
    ("M&A",        ["acquire", "acquisition", "merger", "buyout", "takeover", "deal to buy"]),
    ("Upgrade",    ["upgrade", "raised to", "outperform", "overweight", "buy rating", "price target raised"]),
    ("Downgrade",  ["downgrade", "cut to", "underperform", "underweight", "sell rating", "price target cut"]),
    ("Geopolitics",["war", "sanction", "tariff", "opec", "conflict", "election", "geopolit"]),
    ("Crypto",     ["bitcoin", "ethereum", "crypto", "btc", "etf approval"]),
    ("Legal",      ["lawsuit", "sec charges", "fraud", "settlement", "antitrust", "investigation"]),
]
BULL_WORDS = ["beats", "surge", "soar", "jumps", "rally", "record", "upgrade", "raises", "tops",
              "strong", "growth", "approval", "wins", "gains", "outperform", "bullish"]
BEAR_WORDS = ["misses", "plunge", "slump", "falls", "drops", "downgrade", "cuts", "warns", "weak",
              "lawsuit", "bankruptcy", "recall", "probe", "layoffs", "loss", "bearish", "halts"]


def classify(text):
    t = (text or "").lower()
    category = "General"
    for name, words in CATEGORY_RULES:
        if any(w in t for w in words):
            category = name
            break
    score = sum(w in t for w in BULL_WORDS) - sum(w in t for w in BEAR_WORDS)
    sentiment = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    # impact: more keyword hits / macro categories rank higher (0..100)
    impact = 40
    if category in ("Fed", "Inflation", "Jobs"):
        impact = 85
    elif category in ("Earnings", "M&A", "Geopolitics"):
        impact = 65
    impact = min(100, impact + 8 * abs(score))
    return category, sentiment, impact


def fetch_news():
    if not API_KEYS.get("finnhub"):
        return {"error": "Finnhub key required for live news", "items": []}
    url = "%s/news?category=general&token=%s" % (FINNHUB, urllib.parse.quote(API_KEYS["finnhub"]))
    try:
        raw = http_get_json(url)
    except Exception as e:
        return {"error": "news fetch failed: %s" % e, "items": []}
    items = []
    for n in raw[:60]:
        head = n.get("headline", "")
        cat, sent, impact = classify(head + " " + n.get("summary", ""))
        items.append({
            "headline": head, "source": n.get("source", ""), "url": n.get("url", ""),
            "summary": (n.get("summary", "") or "")[:280], "datetime": n.get("datetime", 0),
            "image": n.get("image", ""), "related": n.get("related", ""),
            "category": cat, "sentiment": sent, "impact": impact,
        })
    items.sort(key=lambda x: (x["impact"], x["datetime"]), reverse=True)
    return {"items": items}


def news_loop():
    while True:
        data = fetch_news()
        if not data.get("error") or not cache_get("news", 1e9):
            cache_set("news", data)
        time.sleep(180)


# ─────────────────────────────────────────────────────────────────────────────
# Calendar  (Finnhub earnings + economic; economic often needs a paid plan)
# ─────────────────────────────────────────────────────────────────────────────
def _date_range(days_ahead=7):
    today = dt.date.today()
    return today.isoformat(), (today + dt.timedelta(days=days_ahead)).isoformat()


# Economic events: free, keyless weekly feed (FairEconomy / ForexFactory JSON).
# Fields per event: title, country (currency code), date (ISO w/ TZ), impact
# (High|Medium|Low|Holiday), forecast, previous, actual.
FAIRECONOMY_FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]
# Filter to these currencies/countries (set CALENDAR_COUNTRIES="" for all).
CALENDAR_COUNTRIES = set(c.strip().upper() for c in os.environ.get(
    "CALENDAR_COUNTRIES", "USD,EUR,GBP,JPY,CNY,CAD").split(",") if c.strip())


def _parse_num(s):
    """Best-effort numeric parse of values like '3.2%', '-0.1', '210K', '1.5M'."""
    if s is None:
        return None
    t = str(s).strip().replace(",", "")
    if t in ("", "-"):
        return None
    mult = 1.0
    if t and t[-1] in "KkMmBbTt":
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}[t[-1].lower()]
        t = t[:-1]
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
    """Pull the free weekly economic calendar and normalize + compute surprise %."""
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
            fc, prev, act = e.get("forecast", ""), e.get("previous", ""), e.get("actual", "")
            f, a = _parse_num(fc), _parse_num(act)
            surprise = round((a - f) / abs(f) * 100, 1) if (f is not None and a is not None and f != 0) else None
            events.append({
                "date": ts[:10], "time": ts, "country": country, "event": e.get("title", ""),
                "impact": e.get("impact", ""), "estimate": fc, "prev": prev,
                "actual": act, "surprise": surprise,
            })
    events.sort(key=lambda x: x["time"])
    return events


def fetch_calendar():
    out = {"earnings": [], "economic": [], "notes": []}
    # Economic events — free keyless feed (no API key needed).
    try:
        out["economic"] = fetch_economic()
        if not out["economic"]:
            out["notes"].append("No economic events for the current window.")
    except Exception as e:
        out["notes"].append("Economic feed unavailable (%s)." % e)
    # Earnings — Finnhub (needs a key).
    if API_KEYS.get("finnhub"):
        frm, to = _date_range(7)
        tok = urllib.parse.quote(API_KEYS["finnhub"])
        try:
            url = "%s/calendar/earnings?from=%s&to=%s&token=%s" % (FINNHUB, frm, to, tok)
            ec = http_get_json(url).get("earningsCalendar", []) or []
            for e in ec[:100]:
                out["earnings"].append({
                    "date": e.get("date"), "symbol": e.get("symbol"),
                    "hour": e.get("hour", ""), "epsEstimate": e.get("epsEstimate"),
                    "epsActual": e.get("epsActual"), "revenueEstimate": e.get("revenueEstimate"),
                    "revenueActual": e.get("revenueActual"),
                })
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
# Screener  (per-symbol quote + Finnhub fundamentals + heuristic scores)
# ─────────────────────────────────────────────────────────────────────────────
def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def fetch_metrics(symbol):
    if not API_KEYS.get("finnhub"):
        return {}
    url = "%s/stock/metric?symbol=%s&metric=all&token=%s" % (
        FINNHUB, urllib.parse.quote(symbol), urllib.parse.quote(API_KEYS["finnhub"]))
    try:
        return http_get_json(url).get("metric", {}) or {}
    except Exception:
        return {}


def screen(symbols):
    rows = []
    use_finnhub = bool(API_KEYS.get("finnhub"))
    for sym in symbols[:25]:
        try:
            q = quote_finnhub(sym, sym) if use_finnhub else quote_mock(sym, sym)
        except Exception:
            q = quote_mock(sym, sym)
        m = fetch_metrics(sym) if use_finnhub else {}
        hi52 = m.get("52WeekHigh") or 0
        lo52 = m.get("52WeekLow") or 0
        price = q.get("last", 0)
        pos52 = clamp(((price - lo52) / (hi52 - lo52) * 100) if hi52 > lo52 else 50)
        chg = q.get("changePercent", 0) or 0
        beta = m.get("beta") or 1.0
        momentum = round(clamp(50 + chg * 6 + (pos52 - 50) * 0.4), 1)
        bullish = round(clamp(50 + chg * 5 + (pos52 - 50) * 0.5), 1)
        bearish = round(clamp(100 - bullish), 1)
        risk = round(clamp(beta * 28 + (100 - pos52) * 0.25), 1)
        rows.append({
            "symbol": sym, "price": price, "changePercent": chg,
            "pe": m.get("peTTM") or m.get("peBasicExclExtraTTM"),
            "pb": m.get("pb"), "ps": m.get("psTTM"),
            "marketCap": m.get("marketCapitalization"),
            "roeTTM": m.get("roeTTM"), "netMargin": m.get("netProfitMarginTTM"),
            "revGrowth": m.get("revenueGrowthTTMYoy"),
            "beta": beta, "high52": hi52, "low52": lo52, "pos52": round(pos52, 1),
            "momentum": momentum, "bullish": bullish, "bearish": bearish, "risk": risk,
            "source": "finnhub" if use_finnhub else "mock",
        })
        if use_finnhub:
            time.sleep(0.2)  # gentle pacing
    return {"rows": rows}


# ─────────────────────────────────────────────────────────────────────────────
# Morning brief  (rule-based; AI narrative if an Anthropic key is set)
# ─────────────────────────────────────────────────────────────────────────────
def _movers(quotes):
    eq = [q for q in quotes if q.get("changePercent") is not None]
    up = sorted(eq, key=lambda q: q["changePercent"], reverse=True)[:3]
    dn = sorted(eq, key=lambda q: q["changePercent"])[:3]
    return up, dn


def build_brief():
    with _quotes_lock:
        quotes = list(_quotes_cache)
    news = (cache_get("news", 1e9) or {}).get("items", [])[:8]
    cal = cache_get("calendar", 1e9) or {}

    def find(sym):
        return next((q for q in quotes if q["symbol"] == sym), None)

    spy, vix = find("SPY"), find("VIX")
    up, dn = _movers(quotes)
    risk_tone = "risk-on" if (spy and spy["changePercent"] > 0) else "risk-off"

    # Rule-based brief (always available)
    lines = []
    if spy:
        lines.append("S&P 500 (SPY) %s%.2f%% at %.2f." % (
            "+" if spy["changePercent"] >= 0 else "", spy["changePercent"], spy["last"]))
    if vix:
        lines.append("VIX %.2f (%s%.2f%%) — %s." % (
            vix["last"], "+" if vix["changePercent"] >= 0 else "", vix["changePercent"],
            "elevated" if vix["last"] > 20 else "calm"))
    if up:
        lines.append("Leaders: " + ", ".join("%s %+.2f%%" % (q["symbol"], q["changePercent"]) for q in up))
    if dn:
        lines.append("Laggards: " + ", ".join("%s %+.2f%%" % (q["symbol"], q["changePercent"]) for q in dn))
    lines.append("Overall tone looks %s." % risk_tone)
    rule_text = " ".join(lines)

    out = {
        "tone": risk_tone, "generatedAt": int(time.time()),
        "movers": {"up": up, "down": dn},
        "headlines": [{"headline": n["headline"], "category": n["category"],
                       "sentiment": n["sentiment"]} for n in news],
        "events": ([e for e in cal.get("economic", []) if e.get("impact") in ("High", "Medium")][:6]
                   or cal.get("economic", [])[:6] or cal.get("earnings", [])[:6]),
        "summary": rule_text,
    }
    return out


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
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path == "/api/quotes":
            with _quotes_lock:
                self._json({"provider": _status["provider"], "updated": _status["updated"],
                            "quotes": list(_quotes_cache)})
        elif path == "/api/news":
            self._json(cache_get("news", 1e9) or fetch_news())
        elif path == "/api/calendar":
            self._json(cache_get("calendar", 1e9) or fetch_calendar())
        elif path == "/api/screener":
            syms = [s.strip().upper() for s in (qs.get("symbols", [""])[0]).split(",") if s.strip()] \
                   or SCREENER_SYMBOLS
            ck = "screener:" + ",".join(syms)
            data = cache_get(ck, 60) or screen(syms)
            cache_set(ck, data)
            self._json(data)
        elif path == "/api/brief":
            self._json(cache_get("brief", 300) or _cache_and_return("brief", build_brief))
        elif path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"index.html not found next to quanta.py", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass


def _cache_and_return(key, fn):
    val = fn()
    cache_set(key, val)
    return val


def main():
    prov = active_provider()
    print("Quanta standalone — morning debrief")
    print("  provider : %s%s" % (prov, "  (no API key set)" if prov == "mock" else ""))
    print("  refresh  : every %ds" % REFRESH_SECONDS)
    print("  open     : http://localhost:%d/" % PORT)
    threading.Thread(target=refresh_loop, daemon=True).start()
    threading.Thread(target=news_loop, daemon=True).start()
    threading.Thread(target=calendar_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
