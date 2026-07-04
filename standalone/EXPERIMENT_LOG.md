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
- **Executed 2026-07-04 (next cycle, per plan). RESULT: REJECTED at both horizons.**
  - h=21d: IC +0.006 (t 0.29) · train +0.048 / test **−0.055** · bootstrap90
    [−0.031, +0.044] · permutation p=0.907 · top3−bottom3 −0.02%
  - h=60d: IC −0.005 (t −0.23) · train +0.050 / test **−0.087** · bootstrap90
    [−0.039, +0.029] · permutation p=0.913 · top3−bottom3 **−0.51%**
  - Four independent methods agree (IC t-stat, bootstrap, permutation, decile
    spread) — no averaging needed; there is nothing to reconcile.
- **Alternative explanations considered:** (a) horizon mismatch — now excluded
  at 10/21/60d; (b) regime dependence — no bucket positive with confidence
  (EXP-10); (c) too few/too-blended assets: 11 internally-diversified ETFs may
  simply not exhibit cross-sectional momentum — most consistent with all data;
  (d) the 2yr pass was multiple-testing luck — likely contributor.
- **Decision (pre-registered consequence executed):** rs weight 0.70 → 0.50;
  composite reframed as DESCRIPTIVE ranking (alphaStatus in the payload);
  registry stage → descriptive; belief confidence 0.55 → 0.15 → 0.05.
- **Limitations:** overlapping weekly sampling (effN 82/28 shown); single
  8yr window; permutation approximates the within-week label shuffle.
- **Follow-up:** none planned — any future RS-alpha claim requires a NEW
  pre-registered experiment on unseen data.

## EXP-12 · 2026-07-04 · RSI(2) replication grid
- **Q:** Does the platform's strongest edge survive attempts to break it?
- **Method:** deep-history replay across years / regimes / vol terciles;
  3×3 parameter perturbation (threshold × exit); frictions (0.10% round-trip
  cost, next-close execution delay, both).
- **Result:** survives everything material — all 9 parameter cells positive
  (PF 1.29–1.76), all vol terciles positive, **delay+cost variant +0.26%/tr
  PF 1.55** (execution-robust). Honest cracks: 2022 −0.2%/tr (n=53), 2020
  flat, Bear-Rally bucket −1.24% (n=10) — the edge is bull/range-market
  mean reversion; the 200-SMA gate mitigates but doesn't eliminate bear risk.
- **Decision:** production confirmed; belief confidence 0.85 → 0.80 with the
  bear-year caveat attached. Parameters unchanged (perturbation ≠ selection).

## Meta-findings (research about our research)
- The **both-windows-positive gate** caught every curve-fit so far (volatility sign, 3m/6m lookbacks, intraday systems).
- **Pre-registration** (EXP-08) is the only defense against post-hoc sign flips.
- 54 weekly cross-sections is enough to reject categories but not to condition on regime — rejection is cheaper than confirmation.
- **Per-instrument baselines** beat absolute thresholds (EXP-05).
- Partial correlation (SPY control, added 2026-07-04) demotes beta-in-disguise factor links — raw ρ overstated driver counts.

## EXP-13 - registered 2026-07-04 - follow-the-filing (congressional buys)
- **Status: PRE-REGISTERED, data accumulating. Written BEFORE results exist.**
- **Q:** Does buying at the DISCLOSURE date of a congressional BUY filing
  (the first date a follower can act - never the trade date) earn positive
  90-calendar-day excess return vs SPY?
- **Method:** every BUY record in congress_trades.json with a disclosure date
  >= 95 days old and loaded price history; entry at first close on/after the
  disclosure date; exit at first close on/after +90d; excess vs SPY over the
  same window. Live readout: /api/government -> pipeline EXP-13.
- **Acceptance gate (fixed now):** n >= 40 matured trades AND hit-rate Wilson
  95% CI excluding 50% AND mean excess > 0. If passed: replicate on NEW
  disclosures (post-pass only) before any production discussion.
- **Prior expectation (recorded for honesty):** academic literature finds
  most of any signal decays before disclosure; base-rate expectation is FAIL.
- Companions (registered, further data-gated): GOV-02 sector-level net
  congressional buying vs forward sector-relative returns (needs >= 26 weekly
  heat snapshots; daily snapshots started 2026-07-04); GOV-03 Federal
  Register rule-count spikes vs sector vol/returns (same snapshot store).

## GOV-04 - registered 2026-07-04 - government event reactions (non-FOMC)
- **Status: DATA-GATED.** No free machine-readable historical archive exists
  for antitrust cases, FDA approvals, tariff announcements, shutdowns,
  sanctions or SEC actions - so the platform logs every dated government
  event (rules, bill stage changes) into congress_trades.json -> events
  (started 2026-07-04) instead of fabricating similarity scores.
- **Gate:** >= 30 archived events of a kind before that kind gets a reaction
  study (same design as the FOMC study: event-day and next-day sector
  returns vs all-days baseline).
- **Measured today:** scheduled FOMC decisions only (published date archive
  2019-2026, 2020 emergency actions excluded). First run n=59: decision-day
  |move| 0.92% vs 0.78% all-days baseline (~1.2x, MODESTLY elevated - less
  than folklore suggests, partly because the 8yr baseline includes 2020/2022
  high-vol days), 51% up -> no directional edge; sizing context at most.
  Read out live at /api/government -> eventStudies.
