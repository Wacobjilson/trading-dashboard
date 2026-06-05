#!/usr/bin/env python3
"""
Walk-forward backtest of the Quanta sector-ETF entry engine.

For every sector ETF it replays history bar-by-bar, calling the SAME analysis
function the live dashboard uses (`analyze_bars`) on a point-in-time slice — so
there is no lookahead. When a fresh "Ready" setup appears it simulates a trade:

  entry  = close on the signal bar (price is in the golden pocket)
  stop   = setup stop (ATR-buffered beyond the swing)
  target = setup target (the prior swing)
  exit   = whichever of {stop, target} is touched first on later bars; if both
           are touched on the same bar we assume the STOP first (conservative);
           otherwise exit at close after MAXHOLD bars.

Results are reported in R-multiples (R = 1 unit of initial risk = |entry-stop|),
which is the right unit because position size scales to risk.

Usage:
  python backtest.py                       # daily + weekly, both directions
  QUANTA_SYNTH_BARS=1 python backtest.py   # run on synthetic bars (no API)
  BT_DIR=long BT_WITH_TREND=1 python backtest.py
  BT_SWEEP=1 python backtest.py            # grid-search stop × target × min_score
  BT_WF=1 BT_DIR=long python backtest.py   # walk-forward: optimize on train, test out-of-sample

Caveats (read these): fills are idealized (no slippage/commission); same-bar
stop+target is resolved as a loss; intrabar path is unknown so touches use bar
high/low; synthetic bars are NOT real market data. Treat output as a sanity check
on the *logic's* edge, not a promise of live performance.
"""

import datetime as dt
import os
import sys
import time

import quanta as q

# Force UTF-8 output so unicode glyphs don't crash on a cp1252 Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WARMUP = {"daily": 210, "weekly": 60}
MAXHOLD = {"daily": 40, "weekly": 16}
TFS = os.environ.get("BT_TF", "daily,weekly").split(",")
DIR_FILTER = os.environ.get("BT_DIR", "both").lower()        # long | short | both
WITH_TREND = q._envbool("BT_WITH_TREND", False)              # only with-trend setups
MIN_SCORE = float(os.environ.get("BT_MIN_SCORE", "55"))


def date_of(bar):
    return dt.datetime.fromtimestamp(bar["t"] / 1000, dt.timezone.utc).date()


def align_spy_daily(sym_bars, spy_bars):
    """Return SPY closes aligned (by date, forward-filled) to sym_bars."""
    m = {date_of(b): b["c"] for b in spy_bars}
    out, last = [], spy_bars[0]["c"]
    for b in sym_bars:
        last = m.get(date_of(b), last)
        out.append(last)
    return out


def align_spy_weekly(sym_weekly, spy_weekly):
    def wk(b):
        return dt.datetime.fromtimestamp(b["t"] / 1000, dt.timezone.utc).isocalendar()[:2]
    m = {wk(b): b["c"] for b in spy_weekly}
    out, last = [], spy_weekly[0]["c"]
    for b in sym_weekly:
        last = m.get(wk(b), last)
        out.append(last)
    return out


def simulate(bars, spy_closes, sym, tf, params, start=None, end=None):
    """Walk forward; return completed trades whose ENTRY bar is in [start, end).
    History before `start` is still used for analysis (no truncation of context)."""
    trades = []
    maxhold = MAXHOLD[tf]
    n = len(bars)
    start = WARMUP[tf] if start is None else max(WARMUP[tf], start)
    end = (n - 1) if end is None else min(n - 1, end)
    i = start
    prev_ready = False
    while i < end:
        a = q.analyze_bars(bars[:i + 1], sym, tf, spy_closes[:i + 1], params)
        ready = a.get("ok") and a["status"] == "Ready"
        if ready and a["direction"] in (("long", "short") if DIR_FILTER == "both" else (DIR_FILTER,)) \
           and (not WITH_TREND or a["bias"] == "with-trend") and not prev_ready:
            direction, entry, stop, target = a["direction"], bars[i]["c"], a["stop"], a["target"]
            risk = abs(entry - stop)
            prev_ready = True
            if risk <= 0:
                i += 1
                continue
            exit_px, exit_j, outcome = None, None, None
            for j in range(i + 1, min(i + maxhold, n - 1) + 1):
                hi, lo = bars[j]["h"], bars[j]["l"]
                if direction == "long":
                    if lo <= stop:
                        exit_px, outcome = stop, "stop"
                    elif hi >= target:
                        exit_px, outcome = target, "target"
                else:
                    if hi >= stop:
                        exit_px, outcome = stop, "stop"
                    elif lo <= target:
                        exit_px, outcome = target, "target"
                if exit_px is not None:
                    exit_j = j
                    break
            if exit_px is None:
                exit_j = min(i + maxhold, n - 1)
                exit_px, outcome = bars[exit_j]["c"], "timeout"
            r = (exit_px - entry) / risk if direction == "long" else (entry - exit_px) / risk
            trades.append({"sym": sym, "tf": tf, "dir": direction, "date": str(date_of(bars[i])),
                           "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
                           "exit": round(exit_px, 2), "R": round(r, 2), "held": exit_j - i,
                           "outcome": outcome, "score": a["score"]})
            i = exit_j + 1   # flat until the trade closes, then re-arm
            prev_ready = False
        else:
            prev_ready = ready
            i += 1
    return trades


def stats(trades):
    n = len(trades)
    if not n:
        return None
    Rs = [t["R"] for t in trades]
    wins = [r for r in Rs if r > 0]
    losses = [r for r in Rs if r <= 0]
    gross_w, gross_l = sum(wins), -sum(losses)
    # max drawdown on the R-equity curve
    eq, peak, mdd = 0.0, 0.0, 0.0
    for r in Rs:
        eq += r
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    # longest losing streak
    streak = worst = 0
    for r in Rs:
        streak = streak + 1 if r <= 0 else 0
        worst = max(worst, streak)
    return {
        "n": n, "win%": round(100 * len(wins) / n, 1),
        "expectancy_R": round(sum(Rs) / n, 3), "total_R": round(sum(Rs), 1),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(gross_w / gross_l, 2) if gross_l > 0 else float("inf"),
        "avg_hold": round(sum(t["held"] for t in trades) / n, 1),
        "max_dd_R": round(mdd, 1), "max_loss_streak": worst,
    }


def fmt_stats(label, s):
    if not s:
        return "%-22s  no trades" % label
    pf = "inf" if s["profit_factor"] == float("inf") else "%.2f" % s["profit_factor"]
    return ("%-22s n=%-4d win%%=%-5s exp=%-+6.3fR  PF=%-5s totalR=%-+7.1f "
            "avgW=%-+5.2f avgL=%-+5.2f maxDD=%-+6.1fR streak=%d hold=%.1f"
            % (label, s["n"], s["win%"], s["expectancy_R"], pf, s["total_R"],
               s["avg_win"], s["avg_loss"], s["max_dd_R"], s["max_loss_streak"], s["avg_hold"]))


def collect(bars, syms, params, mode="all", frac=0.6, tfs=None):
    """Run the walk-forward across timeframes/sectors for one param set.

    mode: 'all' = whole history; 'train' = entries in the first `frac` of bars;
    'test' = entries in the held-out remainder. History before the split is still
    used as analysis context (only the ENTRY date is gated)."""
    trades = []
    use_tfs = tfs if tfs is not None else [t.strip() for t in TFS if t.strip() in WARMUP]
    for tf in use_tfs:
        spy_bars = q.resample_weekly(bars[q.BENCH]) if tf == "weekly" else bars[q.BENCH]
        for s in syms:
            sb = q.resample_weekly(bars[s]) if tf == "weekly" else bars[s]
            if len(sb) <= WARMUP[tf] + 5:
                continue
            spy_aligned = align_spy_weekly(sb, spy_bars) if tf == "weekly" else align_spy_daily(sb, bars[q.BENCH])
            split = int(len(sb) * frac)
            start, end = (None, split) if mode == "train" else (split, None) if mode == "test" else (None, None)
            trades += simulate(sb, spy_aligned, s, tf, params, start, end)
    return trades


def walkforward(bars, syms):
    """Optimize the param grid on the first `frac` of history (train), lock the
    winner, then measure it on the held-out remainder (test) it never saw. Also
    runs the user's current scheme on the same test set as a baseline.

    Daily only — 2 years of weekly bars is too few to split. The honest test of
    whether the sweep found real edge or just curve-fit the past."""
    frac = float(os.environ.get("BT_WF_FRAC", "0.6"))
    min_train = int(os.environ.get("BT_WF_MINTRADES", "20"))
    grid = [(sm, tm, ms)
            for sm in ("fib618", "fib786", "swinglow")
            for tm in ("ext1272", "ext1618", "prior")
            for ms in (45, 55, 65)]

    print("=" * 92)
    print("WALK-FORWARD  —  train=first %.0f%% / test=last %.0f%%  (daily, dir=%s, with_trend=%s)"
          % (frac * 100, (1 - frac) * 100, DIR_FILTER, WITH_TREND))
    print("  Optimize on TRAIN, then evaluate the winner on the unseen TEST. min train trades=%d" % min_train)
    print("=" * 92)

    ranked = []
    for sm, tm, ms in grid:
        p = {"stop_mode": sm, "stop_buf": 0.25, "target_mode": tm, "min_score": ms}
        s = stats(collect(bars, syms, p, mode="train", frac=frac, tfs=["daily"]))
        if s and s["n"] >= min_train:
            ranked.append(((sm, tm, ms), p, s))
    if not ranked:
        print("Not enough train trades to optimize (try a smaller BT_WF_MINTRADES).")
        return
    ranked.sort(key=lambda r: (r[2]["expectancy_R"], r[2]["total_R"]), reverse=True)

    print("\nTRAIN leaderboard (top 6 of %d eligible configs):" % len(ranked))
    for (sm, tm, ms), _p, s in ranked[:6]:
        print(fmt_stats("  %s/%s/%d" % (sm, tm, ms), s))

    best_key, best_p, best_train = ranked[0]
    test = stats(collect(bars, syms, best_p, mode="test", frac=frac, tfs=["daily"]))
    base_p = {"stop_mode": "fib618", "stop_buf": 0.25, "target_mode": "ext1272", "min_score": 55}
    base_test = stats(collect(bars, syms, base_p, mode="test", frac=frac, tfs=["daily"]))
    full_best = stats(collect(bars, syms, best_p, mode="all", frac=frac, tfs=["daily"]))

    print("\n" + "-" * 92)
    print("CHOSEN by TRAIN: stop=%s target=%s min_score=%d" % best_key)
    print(fmt_stats("  TRAIN (in-sample)", best_train))
    print(fmt_stats("  TEST  (OUT-of-sample)", test))
    print(fmt_stats("  baseline your-style TEST", base_test))
    print(fmt_stats("  chosen over FULL period", full_best))

    print("-" * 92)
    if not test:
        verdict = "INCONCLUSIVE — no test trades."
    else:
        held = test["expectancy_R"] > 0 and test["profit_factor"] >= 1.2
        degrade = (best_train["expectancy_R"] - test["expectancy_R"])
        if held and test["expectancy_R"] >= 0.5 * best_train["expectancy_R"]:
            verdict = "HOLDS OUT-OF-SAMPLE — edge survived on unseen data (kept %.0f%% of train expectancy)." % (
                100 * test["expectancy_R"] / best_train["expectancy_R"] if best_train["expectancy_R"] else 0)
        elif test["expectancy_R"] > 0:
            verdict = "MARGINAL — still positive out-of-sample but expectancy decayed %.3fR (likely some overfit)." % degrade
        else:
            verdict = "FAILS — the train winner did NOT carry out-of-sample (overfit / regime-dependent). Trust robust defaults, not the top sweep cell."
    print("VERDICT: " + verdict)
    print("(Single 60/40 split, daily, ~%d test trades — directional evidence, not proof.)" % (test["n"] if test else 0))


def main():
    syms = [s for s, _ in q.SECTORS]
    universe = [q.BENCH] + syms
    print("Loading bars for %d symbols (%s)…" % (len(universe),
          "synthetic" if (q.FORCE_SYNTH or not q.API_KEYS.get("polygon")) else "polygon"))
    bars, src = {}, "synth"
    for s in universe:
        b, src = q.load_bars(s)
        bars[s] = b
        if src == "polygon":
            time.sleep(13)  # respect 5 req/min free tier
    print("  source=%s, bars/symbol≈%d\n" % (src, len(bars[q.BENCH])))

    # ── Walk-forward / out-of-sample validation ──
    if q._envbool("BT_WF", False):
        walkforward(bars, syms)
        return

    # ── Parameter sweep mode ──
    if q._envbool("BT_SWEEP", False):
        grid = [(sm, tm, ms)
                for sm in ("fib618", "fib786", "swinglow")
                for tm in ("ext1272", "ext1618", "prior")
                for ms in (45, 55, 65)]
        print("SWEEP — %d configs (stop × target × min_score), dir=%s, with_trend=%s\n"
              % (len(grid), DIR_FILTER, WITH_TREND))
        results = []
        for sm, tm, ms in grid:
            params = {"stop_mode": sm, "stop_buf": 0.25, "target_mode": tm, "min_score": ms}
            results.append(((sm, tm, ms), stats(collect(bars, syms, params))))
        results.sort(key=lambda r: (r[1]["expectancy_R"] if r[1] else -9, r[1]["total_R"] if r[1] else -9), reverse=True)
        print("%-9s %-8s %-4s | %-5s %-7s %-9s %-6s %-8s %-7s" %
              ("stop", "target", "ms", "n", "win%", "exp(R)", "PF", "totalR", "maxDD"))
        print("-" * 78)
        for (sm, tm, ms), s in results:
            if not s:
                print("%-9s %-8s %-4d | no trades" % (sm, tm, ms)); continue
            pf = "inf" if s["profit_factor"] == float("inf") else "%.2f" % s["profit_factor"]
            print("%-9s %-8s %-4d | %-5d %-7s %-+9.3f %-6s %-+8.1f %-+7.1f" %
                  (sm, tm, ms, s["n"], s["win%"], s["expectancy_R"], pf, s["total_R"], s["max_dd_R"]))
        print("\nTop config by expectancy is the first row. Re-run without BT_SWEEP using "
              "BT_STOP/BT_TGT/BT_MIN_SCORE to see its full per-sector report.")
        return

    # ── Single run (defaults = your style: stop just outside 61.8%, target 1.272 ext) ──
    params = {"stop_mode": os.environ.get("BT_STOP", "fib618"), "stop_buf": 0.25,
              "target_mode": os.environ.get("BT_TGT", "ext1272"), "min_score": int(MIN_SCORE)}
    all_trades = collect(bars, syms, params)

    print("=" * 96)
    print("QUANTA ENTRY BACKTEST  —  entry=50%%  stop=%s(+%.2fATR)  target=%s  min_score=%d  dir=%s  (R=risk)"
          % (params["stop_mode"], params["stop_buf"], params["target_mode"], params["min_score"], DIR_FILTER))
    print("=" * 96)
    for tf in [t.strip() for t in TFS if t.strip() in WARMUP]:
        print(fmt_stats("OVERALL %s" % tf, stats([t for t in all_trades if t["tf"] == tf])))
        for d in ("long", "short"):
            sub = [t for t in all_trades if t["tf"] == tf and t["dir"] == d]
            if sub:
                print(fmt_stats("   %s %s" % (tf, d), stats(sub)))
    print("-" * 96)
    print(fmt_stats("ALL TRADES", stats(all_trades)))
    print("-" * 96)
    print("By sector (all tf):")
    for s in syms:
        st = stats([t for t in all_trades if t["sym"] == s])
        if st:
            print(fmt_stats("   " + s, st))

    # sample of recent trades
    print("-" * 96)
    print("Sample trades (last 12):")
    for t in all_trades[-12:]:
        print("   %-5s %-6s %-5s %s  entry %-8.2f stop %-8.2f tgt %-8.2f exit %-8.2f  %-7s  R=%+.2f  (score %g, %dd)"
              % (t["sym"], t["tf"], t["dir"], t["date"], t["entry"], t["stop"], t["target"],
                 t["exit"], t["outcome"], t["R"], t["score"], t["held"]))


if __name__ == "__main__":
    main()
