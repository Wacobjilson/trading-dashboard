# Institutional Readiness Assessment

**Date:** 2026-07-05 · **Method:** live audit, not summary (SYSTEM_AUDIT.md,
verify score 100/100) · **Bottom line up front:** the *software* is now
provably honest about its numbers (zero-trust verification passes); the
*investment system* remains a **decision-support tool**, not production-grade
for capital, because no strategy has a live track record and the probability
layer is still uncalibrated. Trust the plumbing; do not yet trust the edge.

---

## Subsystem classification

| Subsystem | Class | Conf | Why |
|---|---|---|---|
| Market data (bars/quotes) | **Production Ready** | 92 | Cross-verified 0.00% vs Yahoo/Finnhub; provenance-labeled; stale-not-fabricated; verify guards synth-in-prod |
| Charts | **Production Ready** | 88 | Real bars, source badge; live merge rejects mock/outlier ticks |
| RSI(2) signals | **Conditionally Production Ready** | 70 | Only replicated edge (EXP-12), cross-impl verified — but **zero live trades**; bull/range only |
| Portfolio accounting | **Production Ready** | 85 | Deterministic P&L/R-multiples; decision journal immutable-once-closed |
| Composite score / rotation | **Research Only** | 80 | Correct numbers, **alpha rejected** (EXP-11), labeled descriptive |
| Opportunity Discovery (ODE) | **Research Only** | 72 | 7,299-name scan correct & transparent; strategies staged; outcome-tracked, unproven |
| Deep Value (Phase 19) | **Research Only** | 65 | Real FMP+SEC data, agreement gate & trap-guard work; leverage not sector-adjusted (Z-09); no live theses matured |
| Government Intelligence | **Research Only** | 68 | Point-in-time, delay-disclosed; FOMC dates verified; context-only |
| Options / GEX | **Experimental** | 45 | Dealer convention is an unverifiable assumption (Z-04); IV rank immature |
| Factor engine | **Conditionally Production Ready** | 66 | Partial-corr SPY control fixed beta-in-disguise; thresholds unvalidated |
| Knowledge graph | **Research Only** | 60 | Citation-scanned, every edge verifiable; prose links missed |
| Hybrid RAG | **Conditionally Production Ready** | 70 | BM25+TF-IDF live; vector inactive until embed model pulled; retrieval quality unmeasured |
| AI analyst / MIOS agents | **Research Only** | 62 | Grounded, read-only, safety-enforced; self-assessed confidence weak until scored (gate 20) |
| Decision journal | **Production Ready** | 80 | Correct, immutable, gated stats — needs entries |
| Calibration | **Experimental** | 40 | Logging now scheduled (Phase 15) but not yet 30 matured predictions |
| Verification engine | **Production Ready** | 90 | 14 live checks, critical-fail forces trust 0; in the build gate |
| Background workers | **Production Ready** | 85 | Heartbeat-wrapped; dead-thread detection; 13 alive |

---

## The ten questions, answered with evidence

**1. If I traded directly from this platform today, what could cause me to lose
money because the software is wrong?**
Very little from *software* error now: prices are cross-verified (0.00%),
scores are bounds-checked, RSI(2) is cross-implementation-verified, and synth
data cannot masquerade as real (verify #1). The real loss vectors are
*judgment* traps the software correctly labels but a user might ignore: acting
on GEX flip levels (assumption-rooted, Z-04), sizing on uncalibrated allocation
probabilities, or treating a descriptive score / unproven ODE or deep-value
candidate as a signal. The software would not be *wrong*; the user would be
over-trusting a labeled-uncertain number.

**2. Which subsystem is the weakest link?**
**Options/GEX** — its entire dealer-positioning interpretation rests on the
naive +call/−put convention, unverifiable in free data. Second: **calibration**
(still immature), which is what would license using any probability for sizing.

**3. Which defects are invisible to the user?**
After this phase, far fewer. The two that *were* invisible are now exposed:
futures synth-fallback mislabel (Z-01→fixed, RTY/YM now honest) and mock-quote
chart contamination (Z-02, fixed Phase 15). Remaining semi-invisible: FMP
computes the deep-value ratios (not reproduced from XBRL, Z-05); the leverage
mis-flag on financials is visible-but-unintuitive (Z-09).

**4. Which assumptions have never actually been verified?**
GEX dealer convention; that FMP TTM ratios match the filings; that the ODE
liquidity-gate universe is survivorship-clean historically (forward it is);
that single-stock RSI(2) behaves like the sector-ETF version (explicitly staged
exploratory).

**5. What data is still being approximated?**
GEX dealer inventory (assumption); agency→sector and ticker→sector maps
(curated judgment); reverse-DCF discount/terminal (fixed 10%/2.5%, shown);
RTY/YM intraday (synthetic fallback, now labeled). Everything approximated is
labeled; nothing is silently invented.

**6. What APIs are trusted without independent validation?**
CBOE options (single source, no free cross-check); FMP fundamentals (trusted,
not rebuilt from XBRL — Z-05); FRED (official, trusted); congress.gov/Fed
Register (official). Prices ARE cross-validated (Polygon↔Yahoo↔Finnhub).

**7. Which calculations should be independently reproduced (still)?**
FMP ratios from SEC XBRL (planned Z-05); GEX from a second greeks source (no
free option); portfolio beta and factor betas from an independent stats lib.
RSI(2), scores bounds, and prices already are.

**8. Which AI outputs remain least trustworthy?**
Agent self-assessed confidence (until the n≥20 learning gate grades it);
company-mode answers (no fundamentals in that mode by design); any long-table
arithmetic from a local 14B (never accept computed numbers from AI — all real
numbers are in the payloads). Grounding + citations are enforced structurally.

**9. What would an institutional tech-DD team reject today?**
Zero live/paper track record on the one real edge; uncalibrated probabilities
presented alongside them; single-process/single-key architecture (fine for one
user, fails at scale); options intelligence built on an unverifiable
assumption; no independent XBRL reproduction of fundamentals. They would
*accept*: the verification engine, provenance, cross-provider price checks,
falsification discipline, and the honesty of the labeling.

**10. Ten highest-impact fixes, ranked by operational-risk reduction ÷ effort:**
1. Reach 30 matured predictions → run calibration (already unblocked; just time).
2. Paper-trade RSI(2) via the decision journal → the missing live track record.
3. Sector-adjust the deep-value leverage metric (Z-09) — stop mis-flagging financials.
4. Reproduce 2–3 FMP ratios from SEC XBRL + add a verify cross-check (Z-05).
5. Persist ops/verify counters across restart (Z-08) for real error-trend history.
6. Add a nightly `/api/verify` archive → trust-score trend on the dashboard.
7. Cross-check GEX sign against realized post-flip moves (turn Z-04 into a measured caveat).
8. Investigate RTY/YM intraday source (Z-10) or drop them from the futures grid.
9. Pull `nomic-embed-text` → activate vector RAG + measure retrieval lift.
10. Add per-endpoint latency histograms to ground the "slow endpoint" question.

---

## Final verdict
**Decision-support tool with institutional-grade software honesty.** The
zero-trust layer means: *if a number appears in the app, you can prove where it
came from, reproduce it, and see its confidence* — that standard is met for
prices, RSI(2), scores, probabilities, fundamentals, and filings, and the few
exceptions are explicitly labeled. What separates it from a production
investment system is unchanged and honestly stated: no live track record, no
matured calibration, and options intelligence on an unverifiable assumption.
The path to production runs through fixes #1–#2, not new features.
