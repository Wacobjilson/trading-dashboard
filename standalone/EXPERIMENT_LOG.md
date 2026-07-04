# Experiment Log — institutional memory

Structured record of every experiment. The hypothesis generator references
these IDs (`RESEARCHED_TOPICS` in quanta.py) to prevent duplicate research.
Format: Question / Hypothesis / Method / Data / Result / Limitations / Decision / Follow-up.

---

## EXP-01 · 2026-07-01 · Daily strategy battery
- **Q:** Is there a robust long-only daily edge on the 11 sector ETFs?
- **H:** Documented mean-reversion (Connors RSI2) and momentum systems carry over.
- **Method:** 8 systems, train 60%/test 40%, per-trade %, no lookahead (research.py).
- **Data:** 2yr Polygon daily, 11 sectors.
- **Result:** RSI(2) family survived OOS (~73–75% win, PF ~2, +0.5%/tr). Breakout/momentum failed (PF 1.6, 33% win, deep DD).
- **Limitations:** pre-cost close fills; bull-heavy sample.
- **Decision:** RSI(2)<10 + 200SMA gate → PRODUCTION (Signals tab). Breakout → rejected.
- **Follow-up:** IV-rank entry filter (EXP-gated on options history); regime expectancy via journal.

## EXP-02 · 2026-07-01 · Intraday 15-minute systems
- **Q:** Any 15-min edge on index ETF proxies net of costs?
- **Method:** ORB, VWAP-reversion, intraday RSI2, EMA-cross; 0.02% cost; train/test both-positive gate.
- **Result:** NONE survived; winners in one window lost in the other (sign-flip noise).
- **Decision:** Futures tab = context only. **Negative result retained.**

## EXP-03 · 2026-07-02 · Cross-sectional rotation portfolios
- **Q:** Does holding the top-k sectors by trailing RS beat holding all?
- **Method:** k × lookback grid, monthly rebalance, train/test.
- **Result:** top-3 by **1m** RS survived (train PF 2.88 → test 2.92, n=30); 3m/6m/top-1 decayed.
- **Limitations:** n=30; 1m chosen of 6 variants → selection risk.
- **Decision:** PRODUCTION as labeled candidate; monitored by weekly IC + scorecard.

## EXP-04 · 2026-07-03 · Intel category IC validation
- **Q:** Do the composite's categories predict forward 10d relative returns?
- **Method:** 54 weekly cross-sections, Spearman IC, train/test, redundancy, ablation, bootstrap (research_categories.py).
- **Result:** only `rs` survived (+0.031/+0.017; ablation −0.041 without). trend ρ0.81-redundant; momentum −0.06; volume −0.16; volatility WRONG-SIGNED (IC21 −0.213, t −4.8).
- **Decision:** weights → rs 0.70/options 0.15/macro 0.15; failed cats = zero-weight context.
- **Follow-up:** EXP-08 (inverted volatility); options/macro IC when history allows.

## EXP-05 · 2026-07-03 · PCR calibration defect
- **Q:** Is an absolute P/C-ratio anchor valid across products?
- **Result:** No — SPY structural PCR ~2.5+ read as permanently max-bearish.
- **Decision:** PCR scored as z vs own history (≥20d) else vs sector median. Bug-class lesson: **level thresholds need per-instrument baselines.**

## EXP-06 · 2026-07-03 · Adaptive (regime-conditional) weighting
- **Result:** no regime bucket reaches n≥30 weekly ICs — differences indistinguishable from noise.
- **Decision:** static weights; test runs continuously, verdict auto-flips. (Deep history may change bucket sizes — recheck.)

## EXP-07 · 2026-07-03 · Edge Discovery Lab v1
- **Method:** 156 condition combos, gate = train n≥12/test n≥8/mean>0 both/t≥1.5/beats baseline.
- **Result:** 0 survivors on synthetic (gate sane); real-data survivors are quarantined as watchlist candidates.
- **Decision:** survivors require a quarter of new data before promotion.

## EXP-08 · 2026-07-03 · PRE-REGISTERED: inverted-volatility (high-beta) category
- **H:** high-vol sectors outperform relative in bull tapes (sign-flip of EXP-04's volatility finding).
- **Rule:** test only on data unseen at registration. Not yet run.

## EXP-09 · 2026-07-04 · Live confidence calibration (started)
- **Method:** daily published P(beat SPY 10d) logged; matures at 10 trading days; reliability by bucket; no backfill.
- **Status:** collecting.

## EXP-10 · 2026-07-04 · Deep-history re-validation (this cycle)
- **Q:** Do production conclusions survive on ~8 years (incl. 2020 crash, 2022 bear)?
- **Method:** research matrices switched to Yahoo 25y adjusted daily (quality-checked vs Polygon overlap, diff % stored); all live engines (IC, regimes, probabilities, analogs, counterfactuals, replays) recomputed.
- **Data:** Yahoo v8 chart, common window bounded by XLC inception (2018-06).
- **Result (2026-07-04, 352 weeks / ~2000 sessions, 2018→now):**
  - **RSI(2) STRENGTHENED:** +0.42%/trade, 71% win, PF 1.77, n=639 — through the
    2020 crash and 2022 bear. Now the platform's best-evidenced edge.
  - **RS selection alpha DID NOT replicate:** weekly IC −0.012 (≈0); no regime
    bucket positive with confidence (Trending Bull n=240 → 0.0; Bull Pullback
    n=42 → −0.08). The 2yr IC (+0.031/+0.017) looks sample-specific.
  - **Rotation top-3/1m as a TRADE holds absolutely, not relatively:**
    +1.23%/position PF 1.73 n=252, but counterfactual: top-3 +107% vs SPY-only
    +113% over 352w. Its real measured value = risk-shaping (maxDD −26.6%,
    shallowest of all strategies; SPY −31.2%, bottom-3 −46.4%).
- **Limitations:** Yahoo adjusted closes (methodology may differ slightly from Polygon); live signal paths intentionally unchanged.
- **Decision:** rs composite category → **UNDER REVIEW** in the registry
  (retained for ranking/risk-shaping; allocation's P>50% gate now runs on deep
  base rates and self-corrects). RSI(2) evidence upgraded. Rotation model's
  registry role revised to risk-shaping.
- **Follow-up:** EXP-11.

## EXP-11 · 2026-07-04 · PRE-REGISTERED: RS at longer horizons / risk-adjusted
- **Q:** Does RS ranking carry information at 21/60d horizons, or in
  risk-adjusted form (IC vs vol-scaled forward returns), even though the 10d
  raw IC ≈ 0 on deep data?
- **Rule:** analysis plan fixed before running: Spearman IC at h∈{21,60},
  same weekly states, train/test split at the 60% week; acceptance = positive
  both windows at either horizon. If it fails, rs weight must be reduced and
  the composite redesigned around what remains.
- **Status:** queued — deliberately NOT run in the same cycle that produced
  the anomaly (guard against result-chasing).

## Meta-findings (research about our research)
- The **both-windows-positive gate** caught every curve-fit so far (volatility sign, 3m/6m lookbacks, intraday systems).
- **Pre-registration** (EXP-08) is the only defense against post-hoc sign flips.
- 54 weekly cross-sections is enough to reject categories but not to condition on regime — rejection is cheaper than confirmation.
- **Per-instrument baselines** beat absolute thresholds (EXP-05).
- Partial correlation (SPY control, added 2026-07-04) demotes beta-in-disguise factor links — raw ρ overstated driver counts.
