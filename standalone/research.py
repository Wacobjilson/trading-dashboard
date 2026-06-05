#!/usr/bin/env python3
"""
Strategy research harness for the 11 SPDR sector ETFs.

Goal: find a *robust* edge, not a curve-fit one. It fetches daily bars once, then
runs a battery of well-documented candidate systems and reports each in % terms,
split into TRAIN (first 60% of history) and TEST (held-out last 40%) so you can see
whether the edge survives out-of-sample. Buy-and-hold is shown as the benchmark.

All systems are LONG-ONLY (the walk-forward already showed shorts bleed) and
no-lookahead (every decision uses only data up to that bar). Trades are flat-to-flat
per sector; returns are simple per-trade % (entry close → exit close).

Candidates:
  bh              buy & hold (benchmark)
  rsi2_10         Connors RSI(2)<10, regime close>SMA200, exit close>SMA5
  rsi2_5          RSI(2)<5 (stricter), same regime/exit
  rsi2_run        RSI(2)<10, exit RSI(2)>65 or 8-bar timeout (let winners run)
  rsi2_noreg      RSI(2)<10, NO regime filter (shows the value of the 200SMA gate)
  rsi2_stop       RSI(2)<10 + regime, exit close>SMA5, hard 5% stop
  pull_sma10      close>SMA200 and a fresh cross below SMA10, exit close>SMA10
  breakout20      20-day high close + close>SMA50 (momentum), exit close<SMA20

Run:  python research.py        (uses your Polygon key; ~2.5 min to fetch)
      QUANTA_SYNTH_BARS=1 python research.py   (synthetic, instant — machinery only)
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

TRAIN_FRAC = float(os.environ.get("RS_TRAIN_FRAC", "0.6"))
WARMUP = 200


# ── indicator series (all backward-looking) ──────────────────────────────────
def sma_series(c, n):
    out = [None] * len(c)
    s = 0.0
    for i, v in enumerate(c):
        s += v
        if i >= n:
            s -= c[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rsi_series(c, n=2):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    deltas = [c[i] - c[i - 1] for i in range(1, len(c))]
    ag = sum(d for d in deltas[:n] if d > 0) / n
    al = -sum(d for d in deltas[:n] if d < 0) / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for k in range(n, len(deltas)):
        d = deltas[k]
        ag = (ag * (n - 1) + (d if d > 0 else 0)) / n
        al = (al * (n - 1) + (-d if d < 0 else 0)) / n
        out[k + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


# ── strategies: each returns trades [{sym, entry_i, exit_i, ret, hold, tt}] ──
def _ind(bars):
    c = [b["c"] for b in bars]
    return {"c": c, "sma5": sma_series(c, 5), "sma10": sma_series(c, 10),
            "sma20": sma_series(c, 20), "sma50": sma_series(c, 50),
            "sma200": sma_series(c, 200), "rsi2": rsi_series(c, 2)}


def _tt(i, n):
    return "train" if i < TRAIN_FRAC * n else "test"


def _walk_meanrev(bars, ix, sym, thr, regime, exit_fn, stop=None):
    c = ix["c"]; n = len(c); trades = []; i = WARMUP
    while i < n - 1:
        ok = ix["rsi2"][i] is not None and ix["rsi2"][i] < thr
        if regime:
            ok = ok and ix["sma200"][i] is not None and c[i] > ix["sma200"][i]
        if ok:
            entry = c[i]; j = i + 1
            while j < n:
                stopped = stop is not None and c[j] <= entry * (1 - stop)
                if stopped or exit_fn(ix, j, i) or j == n - 1:
                    break
                j += 1
            trades.append({"sym": sym, "entry_i": i, "exit_i": j, "ret": c[j] / entry - 1,
                           "hold": j - i, "tt": _tt(i, n)})
            i = j + 1
        else:
            i += 1
    return trades


def strat_breakout(bars, ix, sym, lb=20):
    c = ix["c"]; n = len(c); trades = []; i = max(WARMUP, lb)
    while i < n - 1:
        if ix["sma50"][i] is not None and c[i] > ix["sma50"][i] and c[i] >= max(c[i - lb:i]):
            entry = c[i]; j = i + 1
            while j < n - 1 and (ix["sma20"][j] is None or c[j] >= ix["sma20"][j]):
                j += 1
            trades.append({"sym": sym, "entry_i": i, "exit_i": j, "ret": c[j] / entry - 1,
                           "hold": j - i, "tt": _tt(i, n)})
            i = j + 1
        else:
            i += 1
    return trades


def strat_pull_sma10(bars, ix, sym):
    c = ix["c"]; n = len(c); trades = []; i = WARMUP
    while i < n - 1:
        s10, s200 = ix["sma10"][i], ix["sma200"][i]
        crossed = s10 is not None and c[i] < s10 and c[i - 1] >= (ix["sma10"][i - 1] or c[i - 1])
        if s200 is not None and c[i] > s200 and crossed:
            entry = c[i]; j = i + 1
            while j < n - 1 and (ix["sma10"][j] is None or c[j] <= ix["sma10"][j]):
                j += 1
            trades.append({"sym": sym, "entry_i": i, "exit_i": j, "ret": c[j] / entry - 1,
                           "hold": j - i, "tt": _tt(i, n)})
            i = j + 1
        else:
            i += 1
    return trades


def exit_above_sma5(ix, j, i):
    return ix["sma5"][j] is not None and ix["c"][j] > ix["sma5"][j]


def exit_run(ix, j, i):
    return (ix["rsi2"][j] is not None and ix["rsi2"][j] > 65) or (j - i) >= 8


STRATS = {
    "rsi2_10":    lambda b, ix, s: _walk_meanrev(b, ix, s, 10, True, exit_above_sma5),
    "rsi2_5":     lambda b, ix, s: _walk_meanrev(b, ix, s, 5, True, exit_above_sma5),
    "rsi2_run":   lambda b, ix, s: _walk_meanrev(b, ix, s, 10, True, exit_run),
    "rsi2_noreg": lambda b, ix, s: _walk_meanrev(b, ix, s, 10, False, exit_above_sma5),
    "rsi2_stop":  lambda b, ix, s: _walk_meanrev(b, ix, s, 10, True, exit_above_sma5, stop=0.05),
    "pull_sma10": strat_pull_sma10,
    "breakout20": strat_breakout,
}


# ── performance ──────────────────────────────────────────────────────────────
def perf(trades):
    rets = [t["ret"] for t in trades]
    n = len(rets)
    if n == 0:
        return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    # Additive equity (sum of per-trade %): honest when pooling parallel sectors.
    eq, peak, mdd = 0.0, 0.0, 0.0
    for r in rets:
        eq += r
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    gp, gl = sum(wins), -sum(losses)
    std = stcs.pstdev(rets) if n > 1 else 0
    return {"n": n, "win": 100 * len(wins) / n, "avg": 100 * sum(rets) / n,
            "total": 100 * sum(rets), "pf": (gp / gl) if gl > 0 else float("inf"),
            "mdd": 100 * mdd, "hold": sum(t["hold"] for t in trades) / n,
            "sharpe": (sum(rets) / n / std) if std > 0 else 0,
            "exp_win": 100 * (sum(wins) / len(wins)) if wins else 0,
            "exp_loss": 100 * (sum(losses) / len(losses)) if losses else 0}


def row(label, p):
    if not p:
        return "%-26s  no trades" % label
    pf = "inf" if p["pf"] == float("inf") else "%.2f" % p["pf"]
    return ("%-26s n=%-4d win=%-5.1f%% avg=%-+6.2f%% tot=%-+8.1f%% PF=%-5s "
            "maxDD=%-+7.1f%% sharpe=%-+5.2f hold=%.1f"
            % (label, p["n"], p["win"], p["avg"], p["total"], pf, p["mdd"], p["sharpe"], p["hold"]))


def bench_buyhold(bars_map, syms, mode):
    """Equal-weight buy&hold of all sectors over the relevant window."""
    rets = []
    for s in syms:
        c = [b["c"] for b in bars_map[s]]
        if len(c) <= WARMUP + 5:
            continue
        split = int(len(c) * TRAIN_FRAC)
        a, b = (WARMUP, split) if mode == "train" else (split, len(c) - 1) if mode == "test" else (WARMUP, len(c) - 1)
        rets.append(c[b] / c[a] - 1)
    if not rets:
        return None
    return {"n": len(rets), "win": 100 * sum(r > 0 for r in rets) / len(rets),
            "avg": 100 * sum(rets) / len(rets), "total": 100 * sum(rets) / len(rets),
            "pf": float("inf"), "mdd": 0, "hold": 0, "sharpe": 0}


def main():
    syms = [s for s, _ in q.SECTORS]
    print("Loading daily bars for %d sectors (%s)…" %
          (len(syms), "synthetic" if (q.FORCE_SYNTH or not q.API_KEYS.get("polygon")) else "polygon"))
    bars_map = {}
    for s in syms:
        b, src = q.load_bars(s)
        bars_map[s] = b
        if src == "polygon":
            time.sleep(13)
    print("  source=%s, bars/symbol≈%d, train=%.0f%%/test=%.0f%%\n"
          % (src, len(bars_map[syms[0]]), TRAIN_FRAC * 100, (1 - TRAIN_FRAC) * 100))

    # run all strategies, collect trades
    all_tr = {name: [] for name in STRATS}
    for s in syms:
        bars = bars_map[s]
        if len(bars) <= WARMUP + 5:
            continue
        ix = _ind(bars)
        for name, fn in STRATS.items():
            all_tr[name] += fn(bars, ix, s)

    print("=" * 110)
    print("SECTOR-ETF STRATEGY RESEARCH  —  long-only, per-trade %% returns, no lookahead")
    print("=" * 110)
    for mode in ("all", "train", "test"):
        print("\n### %s window ###  (buy&hold benchmark first)" % mode.upper())
        print(row("buy&hold (eq-weight)", bench_buyhold(bars_map, syms, mode)))
        scored = []
        for name in STRATS:
            sub = [t for t in all_tr[name] if mode == "all" or t["tt"] == mode]
            p = perf(sub)
            scored.append((name, p))
        # sort by sharpe within window for readability
        scored.sort(key=lambda x: (x[1]["sharpe"] if x[1] else -9), reverse=True)
        for name, p in scored:
            print(row("  " + name, p))

    # robustness pick: positive test avg + PF>1.1 + enough test trades, ranked by test sharpe
    print("\n" + "=" * 110)
    print("ROBUSTNESS (survives out-of-sample?):")
    cand = []
    for name in STRATS:
        tr = perf([t for t in all_tr[name] if t["tt"] == "train"])
        te = perf([t for t in all_tr[name] if t["tt"] == "test"])
        if te and tr and te["n"] >= 15 and te["avg"] > 0 and te["pf"] > 1.1:
            cand.append((name, tr, te))
    cand.sort(key=lambda x: x[2]["sharpe"], reverse=True)
    if not cand:
        print("  None of the tested systems held up out-of-sample with enough trades.")
        print("  -> the honest answer: no robust daily edge found in this sample. Don't deploy blindly.")
    else:
        for name, tr, te in cand:
            print("  %-12s TRAIN avg=%+.2f%% PF=%.2f  |  TEST avg=%+.2f%% PF=%.2f win=%.0f%% n=%d  (sharpe %.2f)"
                  % (name, tr["avg"], tr["pf"], te["avg"], te["pf"], te["win"], te["n"], te["sharpe"]))
        print("\n  Best surviving candidate: %s" % cand[0][0])


if __name__ == "__main__":
    main()
