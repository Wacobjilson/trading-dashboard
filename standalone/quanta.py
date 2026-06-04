#!/usr/bin/env python3
"""
Quanta standalone — a zero-dependency trading dashboard.

Runs a tiny HTTP server (Python standard library only) that:
  * fetches quotes from Finnhub / Polygon / Alpha Vantage (or synthetic mock data),
  * serves the dashboard at  http://localhost:8000/
  * serves quote JSON at     http://localhost:8000/api/quotes

No pip install, no database, no auth. Just:  python3 quanta.py

Configure by editing API_KEYS below, or set the matching environment variables.
With no key set it runs in MOCK mode (synthetic data) so you can try it instantly.
"""

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
# Config — edit these, or set env vars of the same name.
# ─────────────────────────────────────────────────────────────────────────────
API_KEYS = {
    "polygon": os.environ.get("POLYGON_API_KEY", ""),
    "finnhub": os.environ.get("FINNHUB_API_KEY", ""),
    "alphavantage": os.environ.get("ALPHAVANTAGE_API_KEY", ""),
}
# Pin a provider ("polygon" | "finnhub" | "alphavantage" | "mock"), or "" to
# auto-pick the first one with a key set.
PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "").lower()
PORT = int(os.environ.get("PORT", "8000"))
# How often the server refreshes quotes from the provider (seconds). Keep this
# reasonable to respect free-tier rate limits (Finnhub ~60/min, Alpha Vantage ~5/min).
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "15"))

# ─────────────────────────────────────────────────────────────────────────────
# Instruments. Futures are mapped to liquid ETF proxies so free tiers work.
# fields: (symbol, name, asset_class, {provider: vendor_symbol})
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# Provider selection
# ─────────────────────────────────────────────────────────────────────────────
def active_provider():
    if PROVIDER in ("polygon", "finnhub", "alphavantage", "mock"):
        return PROVIDER
    for name in ("polygon", "finnhub", "alphavantage"):
        if API_KEYS.get(name):
            return name
    return "mock"


def http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "quanta-standalone"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def quote_finnhub(sym, vendor):
    url = "https://finnhub.io/api/v1/quote?symbol=%s&token=%s" % (
        urllib.parse.quote(vendor), urllib.parse.quote(API_KEYS["finnhub"]))
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


# Mock state (random walk), kept across refreshes.
_mock_state = {}


def quote_mock(sym, vendor):
    st = _mock_state.get(sym)
    if st is None:
        base = SEED_PRICES.get(sym, 100.0)
        st = {
            "last": base, "prevClose": base * (1 - (random.random() - 0.5) * 0.01),
            "week": base * (1 - (random.random() - 0.5) * 0.04), "open": base,
            "high": base, "low": base, "vol": random.randint(10_000_000, 40_000_000),
            "avg": random.randint(30_000_000, 80_000_000),
        }
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


PROVIDER_FNS = {
    "finnhub": quote_finnhub, "alphavantage": quote_alphavantage,
    "polygon": quote_polygon, "mock": quote_mock,
}

# ─────────────────────────────────────────────────────────────────────────────
# Background refresher — fetches all instruments every REFRESH_SECONDS.
# Falls back to mock per-symbol if the live provider errors, so the dashboard is
# always fully populated.
# ─────────────────────────────────────────────────────────────────────────────
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
                q = fn(sym, vendor)
                src = provider
            except Exception:
                q = quote_mock(sym, vendor)  # graceful fallback
                src = "mock"
            q.update({"symbol": sym, "name": name, "assetClass": klass, "source": src})
            out.append(q)
            if provider == "alphavantage":
                time.sleep(13)  # crude rate-limit guard for AV free tier
        with _quotes_lock:
            global _quotes_cache
            _quotes_cache = out
            _status["updated"] = int(time.time())
        time.sleep(REFRESH_SECONDS)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP server
# ─────────────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")  # allow file:// usage
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/quotes"):
            with _quotes_lock:
                payload = {"provider": _status["provider"], "updated": _status["updated"],
                           "quotes": list(_quotes_cache)}
            self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path in ("/", "/index.html"):
            path = os.path.join(HERE, "index.html")
            try:
                with open(path, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"index.html not found next to quanta.py", "text/plain")
            return
        self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass  # quiet


def main():
    prov = active_provider()
    print("Quanta standalone")
    print("  provider : %s%s" % (prov, "  (no API key set)" if prov == "mock" else ""))
    print("  refresh  : every %ds" % REFRESH_SECONDS)
    print("  open     : http://localhost:%d/" % PORT)
    threading.Thread(target=refresh_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
