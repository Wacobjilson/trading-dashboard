#!/usr/bin/env python3
"""
Intraday (15-min) edge research for ES/NQ/RTY/YM via ETF proxies (SPY/QQQ/IWM/DIA).

Same discipline as the daily research: no lookahead, TRAIN/TEST split by session,
per-trade % returns, and reported NET of an assumed round-trip slippage cost
(RS_COST, default 0.02%) — intraday edges are thin, so gross numbers are misleading.
All trades are closed by the session end (no overnight; proxies gap).

Systems tested (long and short where it makes sense):
  orb            opening-range (first 30m) breakout, stop at opposite OR, exit EOD
  orb_vwap       same, but only in the direction of price vs VWAP
  vwap_rev       fade a stretch >0.4% beyond session VWAP, exit back at VWAP or EOD
  rsi2_intra     RSI(2)<10 long / >90 short on 15-min, exit RSI(2) back through 50 or EOD
  ema_trend      cross of EMA9/EMA20 in the direction of VWAP, exit opposite cross or EOD

Caveats: ETF proxies are RTH-only (no Globex overnight); real futures differ.
15-min close fills are idealized. This tells you if a *documented* intraday edge
shows up in the cash-index proxy — not a guarantee for live futures.

Run:  python research_futures.py        (real Polygon 15-min; ~1 min for 4 symbols)
      QUANTA_SYNTH_BARS=1 python research_futures.py   (synthetic, machinery only)
"""

import os
import statistics as stcs
import sys
import time

import quanta as q

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DAYS = int(os.environ.get("RS_DAYS", "540"))          # ~2yr of 15-min history
TRAIN_FRAC = float(os.environ.get("RS_TRAIN_FRAC", "0.6"))
COST = float(os.environ.get("RS_COST", "0.0002"))     # round-trip slippage, 0.02%
PROXIES = [("ES", "SPY"), ("NQ", "QQQ"), ("RTY", "IWM"), ("YM", "DIA")]


def rsi_series(c, n=2):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    d = [c[i] - c[i - 1] for i in range(1, len(c))]
    ag = sum(x for x in d[:n] if x > 0) / n
    al = -sum(x for x in d[:n] if x < 0) / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for k in range(n, len(d)):
        ag = (ag * (n - 1) + (d[k] if d[k] > 0 else 0)) / n
        al = (al * (n - 1) + (-d[k] if d[k] < 0 else 0)) / n
        out[k + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def build(proxy):
    bars = q.fetch_intraday(proxy, 15, DAYS)
    sess = q._rth_sessions(bars)
    flat, meta, closes = [], [], []
    for sid, (_date, sb) in enumerate(sess):
        if len(sb) < 4:
            continue
        cum_pv = cum_v = 0.0
        orh = max(sb[0]["h"], sb[1]["h"])
        orl = min(sb[0]["l"], sb[1]["l"])
        base = len(flat)
        for j, b in enumerate(sb):
            tp = (b["h"] + b["l"] + b["c"]) / 3
            cum_pv += tp * b["v"]; cum_v += b["v"]
            flat.append(b); closes.append(b["c"])
            meta.append({"sid": sid, "k": j, "n": len(sb), "base": base,
                         "vwap": cum_pv / cum_v if cum_v else b["c"], "orh": orh, "orl": orl})
    ema9 = q.ema_series(closes, 9)
    ema20 = q.ema_series(closes, 20)
    r2 = rsi_series(closes, 2)
    # group flat indices by session
    sess_idx = {}
    for i, m in enumerate(meta):
        sess_idx.setdefault(m["sid"], []).append(i)
    nsess = len(sess_idx)
    return {"flat": flat, "meta": meta, "ema9": ema9, "ema20": ema20, "r2": r2,
            "sess_idx": sess_idx, "nsess": nsess}


def _tt(sid, nsess):
    return "train" if sid < TRAIN_FRAC * nsess else "test"


def _exit_long(flat, idxs, k0, stop):
    for i in idxs[k0 + 1:]:
        if flat[i]["l"] <= stop:
            return stop
    return flat[idxs[-1]]["c"]


def _exit_short(flat, idxs, k0, stop):
    for i in idxs[k0 + 1:]:
        if flat[i]["h"] >= stop:
            return stop
    return flat[idxs[-1]]["c"]


def strat(name, D):
    flat, meta, ema9, ema20, r2 = D["flat"], D["meta"], D["ema9"], D["ema20"], D["r2"]
    trades = []
    for sid, idxs in D["sess_idx"].items():
        tt = _tt(sid, D["nsess"])
        orh, orl = meta[idxs[0]]["orh"], meta[idxs[0]]["orl"]
        done = False
        for k, i in enumerate(idxs):
            if done:
                break
            c = flat[i]["c"]; vw = meta[i]["vwap"]
            if name in ("orb", "orb_vwap") and k >= 2:
                if c > orh and (name == "orb" or c > vw):
                    ex = _exit_long(flat, idxs, k, orl); trades.append((sid, tt, ex / c - 1)); done = True
                elif c < orl and (name == "orb" or c < vw):
                    ex = _exit_short(flat, idxs, k, orh); trades.append((sid, tt, c / ex - 1)); done = True
            elif name == "vwap_rev" and 1 <= k < idxs.__len__() - 1:
                if c < vw * (1 - 0.004):       # stretched below VWAP -> buy reversion
                    ex = None
                    for i2 in idxs[k + 1:]:
                        if flat[i2]["h"] >= meta[i2]["vwap"]:
                            ex = meta[i2]["vwap"]; break
                    ex = ex if ex is not None else flat[idxs[-1]]["c"]
                    trades.append((sid, tt, ex / c - 1)); done = True
                elif c > vw * (1 + 0.004):      # stretched above -> short reversion
                    ex = None
                    for i2 in idxs[k + 1:]:
                        if flat[i2]["l"] <= meta[i2]["vwap"]:
                            ex = meta[i2]["vwap"]; break
                    ex = ex if ex is not None else flat[idxs[-1]]["c"]
                    trades.append((sid, tt, c / ex - 1)); done = True
            elif name == "rsi2_intra" and k >= 1 and r2[i] is not None:
                if r2[i] < 10:
                    ex = None
                    for i2 in idxs[k + 1:]:
                        if r2[i2] is not None and r2[i2] > 50:
                            ex = flat[i2]["c"]; break
                    ex = ex if ex is not None else flat[idxs[-1]]["c"]
                    trades.append((sid, tt, ex / c - 1)); done = True
                elif r2[i] > 90:
                    ex = None
                    for i2 in idxs[k + 1:]:
                        if r2[i2] is not None and r2[i2] < 50:
                            ex = flat[i2]["c"]; break
                    ex = ex if ex is not None else flat[idxs[-1]]["c"]
                    trades.append((sid, tt, c / ex - 1)); done = True
            elif name == "ema_trend" and k >= 1 and ema9[i] and ema20[i] and ema9[i - 1] and ema20[i - 1]:
                up = ema9[i] > ema20[i] and ema9[i - 1] <= ema20[i - 1]
                dn = ema9[i] < ema20[i] and ema9[i - 1] >= ema20[i - 1]
                if up and c > vw:
                    ex = flat[idxs[-1]]["c"]; trades.append((sid, tt, ex / c - 1)); done = True
                elif dn and c < vw:
                    ex = flat[idxs[-1]]["c"]; trades.append((sid, tt, c / ex - 1)); done = True
    # subtract round-trip cost
    return [(sid, tt, r - COST) for (sid, tt, r) in trades]


STRATS = ["orb", "orb_vwap", "vwap_rev", "rsi2_intra", "ema_trend"]


def perf(rets):
    n = len(rets)
    if n == 0:
        return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    eq = peak = mdd = 0.0
    for r in rets:
        eq += r; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    gp, gl = sum(wins), -sum(losses)
    std = stcs.pstdev(rets) if n > 1 else 0
    return {"n": n, "win": 100 * len(wins) / n, "avg": 100 * sum(rets) / n,
            "total": 100 * sum(rets), "pf": (gp / gl) if gl > 0 else float("inf"),
            "mdd": 100 * mdd, "sharpe": (sum(rets) / n / std) if std > 0 else 0}


def row(label, p):
    if not p:
        return "%-22s no trades" % label
    pf = "inf" if p["pf"] == float("inf") else "%.2f" % p["pf"]
    return ("%-22s n=%-5d win=%-5.1f%% avg=%-+7.3f%% tot=%-+8.1f%% PF=%-5s maxDD=%-+7.1f%% sharpe=%-+5.2f"
            % (label, p["n"], p["win"], p["avg"], p["total"], pf, p["mdd"], p["sharpe"]))


def main():
    print("Loading 15-min bars for %d proxies (%s), ~%d days…" %
          (len(PROXIES), "synthetic" if (q.FORCE_SYNTH or not q.API_KEYS.get("polygon")) else "polygon", DAYS))
    data = {}
    for sym, proxy in PROXIES:
        data[sym] = build(proxy)
        if not (q.FORCE_SYNTH or not q.API_KEYS.get("polygon")):
            time.sleep(13)
    nb = sum(len(d["flat"]) for d in data.values())
    print("  bars=%d, sessions/sym≈%d, cost=%.3f%% round-trip, train=%.0f%%/test=%.0f%%\n"
          % (nb, list(data.values())[0]["nsess"], COST * 100, TRAIN_FRAC * 100, (1 - TRAIN_FRAC) * 100))

    # pool trades across the 4 proxies per strategy
    pooled = {name: [] for name in STRATS}
    for sym in data:
        for name in STRATS:
            pooled[name] += strat(name, data[sym])

    print("=" * 104)
    print("INTRADAY (15-min) FUTURES-PROXY RESEARCH  —  NET of %.3f%% cost, no lookahead" % (COST * 100))
    print("=" * 104)
    for mode in ("all", "train", "test"):
        print("\n### %s ###" % mode.upper())
        scored = []
        for name in STRATS:
            rr = [r for (sid, tt, r) in pooled[name] if mode == "all" or tt == mode]
            scored.append((name, perf(rr)))
        scored.sort(key=lambda x: (x[1]["sharpe"] if x[1] else -9), reverse=True)
        for name, p in scored:
            print(row("  " + name, p))

    print("\n" + "=" * 104)
    print("ROBUSTNESS — a real edge must be positive in BOTH train AND test (consistency),")
    print("not just flip sign between windows. Bar: train & test avg>0, both PF>1.1, test n>=30, net of cost.")
    surv = []
    for name in STRATS:
        te = perf([r for (sid, tt, r) in pooled[name] if tt == "test"])
        tr = perf([r for (sid, tt, r) in pooled[name] if tt == "train"])
        if (te and tr and te["n"] >= 30 and te["avg"] > 0 and te["pf"] > 1.1
                and tr["avg"] > 0 and tr["pf"] > 1.1):
            surv.append((name, tr, te))
    surv.sort(key=lambda x: x[2]["sharpe"], reverse=True)
    if not surv:
        print("  None survived (no strategy was consistently positive across both windows net of cost).")
        print("  -> Honest answer: no robust intraday edge in this 15-min proxy data. Keep Futures as CONTEXT,")
        print("     not a signal. (Free-tier intraday history is also short here — small-sample caveat.)")
    else:
        for name, tr, te in surv:
            print("  %-12s TRAIN avg=%+.3f%% PF=%.2f | TEST avg=%+.3f%% PF=%.2f win=%.0f%% n=%d (sharpe %.2f)"
                  % (name, tr["avg"], tr["pf"], te["avg"], te["pf"], te["win"], te["n"], te["sharpe"]))
        print("\n  Best surviving intraday candidate: %s" % surv[0][0])


if __name__ == "__main__":
    main()
