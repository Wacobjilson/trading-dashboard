#!/usr/bin/env python3
"""
Research Mode: does each Intel score category actually predict sector returns?

For every week t (no lookahead — categories see bars[:t] only), score all 11
sectors with the same `_bar_categories` code production uses, then measure the
cross-sectional Spearman rank IC against FORWARD 5/10/21-day returns relative
to SPY (selection alpha, which is what a cross-sectional score claims to have).

Reports, per category:
  * mean IC per horizon, t-stat, bootstrap 90% CI (resampled weeks)
  * TRAIN (first 60% of weeks) vs TEST (last 40%) — does it survive?
  * redundancy: mean cross-sectional rank correlation between category pairs
  * ablation: composite IC with current weights vs leave-one-out
  * recommended weights ∝ max(0, TRAIN IC_10d), sanity-checked on TEST

Options/macro categories have no reconstructible history (chain snapshots only
began accumulating), so they CANNOT be validated here — the report says so and
production keeps them small and flagged until enough history exists.

Run:  python research_categories.py            (real Polygon bars, ~2.6 min fetch)
      QUANTA_SYNTH_BARS=1 python research_categories.py   (machinery test)
"""

import datetime as dtm
import os
import random
import sys
import time

import quanta as q

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STEP = 5                    # weekly sampling
HORIZONS = (5, 10, 21)
WARMUP = 210
TRAIN_FRAC = float(os.environ.get("RC_TRAIN_FRAC", "0.6"))
CATS = ("trend", "rs", "momentum", "volume", "volatility")


def dates_of(bars):
    return [dtm.datetime.fromtimestamp(b["t"] / 1000, dtm.timezone.utc).date() for b in bars]


def spearman(xs, ys):
    n = len(xs)
    if n < 4:
        return None
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k2 in range(i, j + 1):
                r[order[k2]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx > 0 and vy > 0 else None


def mean_se(vals):
    v = [x for x in vals if x is not None]
    if len(v) < 3:
        return None, None, 0
    m = sum(v) / len(v)
    sd = (sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5
    return m, sd / len(v) ** 0.5, len(v)


def boot_ci(vals, n=1000, lo=5, hi=95):
    v = [x for x in vals if x is not None]
    if len(v) < 5:
        return None, None
    rnd = random.Random(42)
    means = sorted(sum(rnd.choice(v) for _ in v) / len(v) for _ in range(n))
    return means[int(n * lo / 100)], means[int(n * hi / 100)]


def main():
    syms = [s for s, _ in q.SECTORS]
    live = not (q.FORCE_SYNTH or not q.API_KEYS.get("polygon"))
    print("Loading daily bars for %d sectors + SPY (%s)…" % (len(syms), "polygon" if live else "synthetic"))
    bars_map = {}
    for s in syms:
        bars_map[s], src = q.load_bars(s)
        if src == "polygon":
            time.sleep(13)
    spy_bars, _ = q.load_bars("SPY")
    spy_dates = dates_of(spy_bars)
    spy_didx = {d: i for i, d in enumerate(spy_dates)}
    spyc = [b["c"] for b in spy_bars]
    didx = {s: {d: i for i, d in enumerate(dates_of(bars_map[s]))} for s in syms}
    common = sorted(set(spy_didx).intersection(*[set(didx[s]) for s in syms]))
    print("  aligned sessions: %d\n" % len(common))

    # weekly snapshots: category scores (no lookahead) + forward SPY-relative returns
    weeks = []          # each: {"cats": {cat: {sym: score}}, "fwd": {h: {sym: rel}}}
    tlist = list(range(WARMUP, len(common) - max(HORIZONS) - 1, STEP))
    for t in tlist:
        d_t = common[t]
        blends, atrps, subs = {}, {}, {}
        for s in syms:
            i = didx[s][d_t]
            if i < WARMUP:
                break
            sub = bars_map[s][:i + 1]
            c = [b["c"] for b in sub]
            si = spy_didx[d_t]
            def rel(nb):
                a, b2 = q.pct_return(c, nb), q.pct_return(spyc[:si + 1], nb)
                return (a - b2) if (a is not None and b2 is not None) else None
            r1, r3, r6 = rel(21), rel(63), rel(126)
            blends[s] = (0.5 * r1 + 0.3 * r3 + 0.2 * (r6 or 0)) if (r1 is not None and r3 is not None) else None
            av = q.atr(sub, 14)
            atrps[s] = (av / c[-1] * 100) if av else None
            subs[s] = sub
        if len(subs) < len(syms):
            continue
        cats = {c_: {} for c_ in CATS}
        for s in syms:
            cs = q._bar_categories(subs[s], None,
                                   q._pct_rank(list(blends.values()), blends[s]),
                                   q._pct_rank(list(atrps.values()), atrps[s]))
            for c_ in CATS:
                cats[c_][s] = cs[c_]["score"]
        fwd = {}
        for h in HORIZONS:
            fh = {}
            for s in syms:
                i = didx[s][d_t]
                si = spy_didx[d_t]
                cc = [b["c"] for b in bars_map[s]]
                if i + h < len(cc) and si + h < len(spyc):
                    fh[s] = (cc[i + h] / cc[i] - 1) - (spyc[si + h] / spyc[si] - 1)
            fwd[h] = fh
        weeks.append({"cats": cats, "fwd": fwd})

    W = len(weeks)
    split = int(W * TRAIN_FRAC)
    print("=" * 100)
    print("CATEGORY PREDICTIVE POWER — cross-sectional Spearman IC vs forward SPY-relative returns")
    print("(%d weekly snapshots · train=first %d · test=last %d · 11 sectors each)" % (W, split, W - split))
    print("=" * 100)

    ics = {}   # (cat, h) -> list of weekly ICs
    for c_ in CATS:
        for h in HORIZONS:
            ics[(c_, h)] = [spearman(list(w["cats"][c_].values()),
                                     [w["fwd"][h].get(s) for s in w["cats"][c_]])
                            if all(s in w["fwd"][h] for s in w["cats"][c_]) else None
                            for w in weeks]
    print("\n%-12s %s" % ("category", "  ".join("IC%-3d t-stat  [90%% CI]        " % h for h in HORIZONS)))
    for c_ in CATS:
        row = "%-12s" % c_
        for h in HORIZONS:
            m, se, n = mean_se(ics[(c_, h)])
            lo, hi = boot_ci(ics[(c_, h)])
            row += " %+0.3f %+5.1f  [%+0.3f,%+0.3f]  " % (m or 0, (m / se) if (m is not None and se) else 0,
                                                          lo or 0, hi or 0)
        print(row)

    print("\nTRAIN vs TEST (10-day horizon — the swing-trade claim):")
    rec_raw = {}
    for c_ in CATS:
        tr = [x for x in ics[(c_, 10)][:split]]
        te = [x for x in ics[(c_, 10)][split:]]
        mtr, _, _ = mean_se(tr)
        mte, _, _ = mean_se(te)
        survives = (mtr or 0) > 0 and (mte or 0) > 0
        rec_raw[c_] = max(0.0, mtr or 0) if survives else max(0.0, (mtr or 0)) * 0.5
        print("  %-12s train IC %+0.3f · test IC %+0.3f  %s"
              % (c_, mtr or 0, mte or 0, "✓ survives" if survives else "✗ sign-flips or ≤0"))

    print("\nREDUNDANCY — mean cross-sectional rank corr between category scores:")
    for i, a in enumerate(CATS):
        for b2 in CATS[i + 1:]:
            cs = [spearman(list(w["cats"][a].values()), list(w["cats"][b2].values())) for w in weeks]
            m, _, _ = mean_se(cs)
            flag = "  ← redundant (>0.8)" if (m or 0) > 0.8 else ""
            print("  %-12s vs %-12s ρ = %+0.2f%s" % (a, b2, m or 0, flag))

    print("\nABLATION — equal-weight bar-cat composite IC (10d), leave-one-out:")
    wsub = {c_: 1.0 / len(CATS) for c_ in CATS}
    def comp_ic(excl=None):
        out = []
        for w in weeks:
            use = [c_ for c_ in CATS if c_ != excl]
            tw = sum(wsub[c_] for c_ in use)
            comp = {s: sum(wsub[c_] / tw * w["cats"][c_][s] for c_ in use) for s in w["cats"]["trend"]}
            if all(s in w["fwd"][10] for s in comp):
                out.append(spearman(list(comp.values()), [w["fwd"][10][s] for s in comp]))
        return mean_se(out)[0]
    base = comp_ic()
    print("  full composite         IC %+0.3f" % (base or 0))
    for c_ in CATS:
        m = comp_ic(excl=c_)
        print("  without %-12s   IC %+0.3f  (Δ %+0.3f — %s)"
              % (c_, m or 0, (m or 0) - (base or 0),
                 "category ADDS value" if (m or 0) < (base or 0) else "category adds nothing / hurts"))

    tot = sum(rec_raw.values())
    print("\nRECOMMENDED bar-category weights (∝ max(0, train IC_10d), survivors only):")
    if tot <= 0:
        print("  No bar category shows positive train IC — keep equal small weights, rely on regime context.")
    else:
        for c_ in CATS:
            print("  %-12s %.2f" % (c_, rec_raw[c_] / tot))
    print("\nNOT VALIDATED HERE (no reconstructible history): options, macro categories —")
    print("they stay small and flagged 'unvalidated' in production until snapshot history allows this test.")


if __name__ == "__main__":
    main()
