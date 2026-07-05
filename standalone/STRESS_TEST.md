# Institutional Stress Test — 2026-07-04

**Question:** would this system survive real institutional capital scrutiny?
**Verdict up front: NO — and it isn't supposed to yet.** This is a
**decision-support tool with genuinely institutional research discipline**,
not a production-grade investment system. Evidence below. Measurements were
taken against the live deployment on 2026-07-04.

---

## 1. Adversarial audit by subsystem
(Severity / Likelihood / Detectability-in-production)

### Market Intelligence (composite score)
- **Alpha claim already falsified and disclosed** (EXP-11) — the composite is
  descriptive. This is a strength: the system attacked itself first.
- Weights 0.50/0.25/0.25: the 0.25 options and 0.25 macro components are
  **unvalidated** (options IC test at 12/60 snapshot days). A descriptive
  ranking whose components are 50% unvalidated. Med / Certain / High (it says
  so on the tab).
- Fragile thresholds: score≥55 allocation gate, risk<70 — arbitrary,
  disclosed as heuristics. Low / Certain / High.

### Options / GEX
- **Naive dealer convention (+call/−put)** is an assumption, not a measurement
  — real dealer inventory is unobservable in free data (disclosed). GEX flip
  levels can be wrong in exactly the moments they matter. **High / Medium /
  Low** — the worst detectability profile in the price-path systems.
- CBOE delayed 15 min; ivRank/pcrZ need ≥20 snapshots (present: 12 days).
- No lookahead found: history features accumulate point-in-time snapshots.

### Factor engine
- Partial-correlation SPY control (added Phase 7) fixed the beta-in-disguise
  problem — verified in code. |Δρ|≥0.4 break flags are unvalidated thresholds.
- FRED additive-index transform (level → 100+Δ) is an implicit smoothing
  choice; documented in FACTOR_LIBRARY.md. Low / Certain / High.

### Government intelligence
- **FOMC_DECISIONS dates were hand-carried from published schedules without a
  primary-source verification step.** If even 2–3 of 59 dates are wrong, the
  event study silently degrades. **High / Low-Medium / LOW — top-10 risk.**
- Congressional trades: disclosure-lag reconstruction risk is real but
  **correctly engineered around** — heat/event snapshots are point-in-time
  precisely so GOV-02/03/04 can't leak. Verified in congress_loop.
- Survivorship: CONGRESS_SECTOR_MAP is a curated list of today's mega-caps;
  performance enrichment only covers the 25 most-disclosed tickers. Member
  stats are n-gated, but "performance since trade" columns overrepresent
  survivors. Med / Certain / Med (dashes shown for uncovered).
- FMP schema drift would silently stop new records (tolerant field mapping,
  broad excepts). Med / Medium / Med (status line would show stale fetchedAt).

### RSI(2) strategy — the only production edge
- **Selection effect is real**: RSI(2) emerged after EXP-01/02/03 tested
  breakout/intraday/lookback families. Dozens of implicit hypotheses → the
  edge's true p-value is worse than any single test suggests.
- **Mitigation is also real**: replicated on 8yr including 2020/2022, survives
  3×3 parameter grid, 0.10% costs, next-close execution (EXP-12). This is the
  correct antidote to selection.
- **Honest cracks on record**: 2022 ≈ −0.2%/trade, Bear-Rally bucket negative
  (n=10). It is a bull/range edge with a 200-SMA gate, not an all-weather one.
- **Live n = 0.** Zero live or paper trades logged. Backtest→live slippage
  unmeasured. **This alone bars production classification.**
  High / Certain / High (journal will measure it — if used).

### Portfolio construction
- Gate logic (P>50% + Wilson CIs on deep base rates) correctly withholds
  overweights — conservative by evidence, good.
- **Calibration pipeline is starved: 1 logged prediction.** `_pred_log` fires
  only inside `allocation_view()`, which runs only when the Portfolio tab is
  opened. Demand-driven logging means calibration may NEVER mature.
  **High / Certain / Low — this is Fix #1.**

### Research Director / meta layer
- Backlog dimension scores are curated judgments (disclosed). Meta-learning
  keyword classification mislabels nuanced outcomes ("mixed" bucket = 8 of 14).
  Low / Certain / High.

### RAG / AI analyst
- Grounding + section-citation + UNAVAILABLE-instead-of-fabricate verified
  live (cold-cache test produced "UNAVAILABLE", not numbers). Hallucination
  remains possible; output is never parsed back into state (verified: no code
  path). Anchoring-on-AI-prose is a user-behavior risk, not a code one.
  Med / Medium / Med.
- Committee mode ≈ 8 × ~100s ≈ **13+ minutes** on qwen3:14b. UX, not risk.

### Decision journal
- Symbol-matched outcome attachment assumes one open thesis per symbol
  (disclosed). Stats gated n≥10. Sound design, zero data.

---

## 2. Walk-forward integrity
- **Time boundaries**: RSI(2) replay enters at signal close — same-day
  execution is optimistic; the delay+cost variant (+0.26%/tr, PF 1.55) is the
  honest number and is on record. Rotation/regime/probabilities use
  backward-looking features; overlap-adjusted effN shown. Weekly IC harness
  splits train/test chronologically. **No lookahead defects found.**
- **Determinism**: EXP-11 uses `random.Random(11)` — reproducible (verified).
  The "permutation" is a sign-flip approximation, labeled as such — a
  methodological softness, not an error. Synthetic demo bars use `hash(symbol)`
  → **not reproducible across restarts** (PYTHONHASHSEED) — demo-only, trivial.
- **Backtest vs live vs cache**: bars source (polygon/deep/synth) is stamped
  on every payload. Deep cache refreshes weekly → replays drift with the
  window (inherent, disclosed). **Live-vs-backtest comparison is impossible
  today: no live trades exist.**
- Yahoo adjusted closes: methodology unverified beyond the 0.52% Polygon
  overlap diff; retroactive adjustment is a small structural lookahead common
  to all adjusted-price research. Disclosed in DATA_SOURCES.md.

## 3. Data lineage
Traceable end-to-end (source → transform → UI, documented): bars, RSI(2)
signals, options greeks→GEX (given the sign convention), FRED factors,
congressional records (source/timestamps/delay on every row), Fed Register,
bills, probabilities (Wilson/effN), allocation gates. **Flagged NOT
production-grade lineage:**
- GEX dealer-positioning interpretation (assumption at the root of the tree).
- FOMC date list (no primary-source verification step).
- "Expected market impact"-type fields: deliberately absent — correct.

## 4. Model independence
- rotation ≡ rs category ≡ composite momentum: **same signal, three costumes**
  (trend was measured ρ0.81-redundant and retired; rotation's value is
  risk-shaping only, on record). Treat as ONE momentum family.
- RSI(2): genuinely different axis (short-horizon mean reversion vs
  cross-sectional momentum) — the only real diversification in the system.
- Options/macro categories: independence unknown until validated.
- Government: context-only, uncorrelated by policy (never scored).

## 5. Overfitting & multiple testing — confidence discounts
- Families tested to date ≈ 8 categories + 156 edge-lab combos + 3 strategy
  families + horizons/lookbacks ⇒ effective hypotheses O(10²).
- **RSI(2): discount to ~0.7× of backtest expectancy** (selection survived
  replication; bear-regime crack; zero live trades).
- Composite/rotation: no discount needed — alpha claim already retired.
- Options/gov/factor thresholds: treat all current readings as exploratory
  (discount to zero until their pre-registered gates run).
- Edge-lab: t≥1.5 across 156 combos ⇒ expect false survivors; quarterly
  re-verification is already a backlog item — enforce it.

## 6. Latency & production stress (measured 2026-07-04)
- Warm cache: **3–5 ms** across all 12 key endpoints. Cold worst: government
  0.74s (network), scorecard 0.15s. Parallel uncached requests: no stampede
  pathology at this scale (2×analogs: 129ms each). Memory: **162 MiB**.
- AI: ~90–110s/call (14b local), committee ≈ 13 min, cancellable, cached 10min.
- **1 user (design point): comfortably fine. 100 users: fails** — unbounded
  thread-per-connection, per-request heavy views on cache expiry, one Polygon
  key (5 req/min), one Ollama. **1000 users: not a meaningful question for a
  single-file personal tool.** This is honest scope, not a defect — but it
  bounds the classification.
- Zero automated tests at ~7,000 lines / 220 functions. The mock-quote fake-
  bar bug shipped and was caught by the USER, not by tooling. **High / Certain
  / Low — Fix #3.**

## 7. Calibration reality check
- Allocation probabilities = historical base rates (Wilson-bounded), not
  calibrated forecasts. **1 matured-able prediction logged** (needs ≥30).
- Decision journal: 0 scored decisions. Regime classifier: descriptive,
  backward-looking, explicitly not a forecast.
- **Every probability-shaped number in the system is currently UNCALIBRATED
  and correctly labeled as such.** Nothing may be treated as a probability
  until the pipeline matures — which requires Fix #1.

## 8. Would we trust this with money?
- **Production-ready (as tooling):** data plumbing with honest degradation
  (post mock-quote fix), alert engine, portfolio accounting/journal, delayed-
  disclosure handling, research/validation infrastructure itself, AI layer's
  safety boundaries.
- **Research-grade (use for context, never sizing):** composite ranking,
  rotation risk-shaping, factor attribution, probabilities/analogs,
  government intelligence, FOMC event study (pending date verification).
- **Experimental (no reads until gates):** options category, macro category,
  EXP-08/13, GOV-02/03/04, decision-journal stats, hybrid-RAG "better"
  claim, edge-lab survivors.
- **Untrusted for capital:** any live position sizing from the allocation
  engine (uncalibrated); GEX flip levels as actionable levels; anything from
  the AI analyst not verified against payloads.
- **RSI(2): paper-trade candidate.** The evidence is the strongest in the
  system, but institutional standard requires a live/paper track record and
  the bear-regime crack priced in. Smallest-size paper trading through the
  journal is the correct next step — not capital.

---

## A. Top-10 risks (impact × likelihood × undetectability)
1. Calibration starvation — predictions only log when a tab is opened (silent, permanent).
2. Zero automated tests on a 7k-line single file that changes weekly (regressions ship; user is the test suite).
3. FOMC date list unverified against primary source (silently corrupt study).
4. GEX dealer-sign assumption at the root of the options tree (wrong exactly when it matters).
5. RSI(2) selection effect + zero live trades (backtest→live gap unmeasured).
6. Silent-failure paths: 6 broad `except: pass` sites incl. event-archive logging (evidence quietly stops accumulating).
7. Yahoo deep-history dependency: unofficial API, adjustment methodology semi-verified (0.52% overlap only).
8. FMP schema drift → new congressional records silently stop (status shows stale time only).
9. Unvalidated 0.25+0.25 composite weights displayed with a validated-looking number.
10. Human anchoring on AI prose / descriptive scores despite labels (behavioral, unmeasurable).

## B. Kill list (if this were a hedge fund today)
- **GEX flip/wall levels as tradable levels** — assumption-rooted; keep as context research only.
- **Options + macro composite weights** — set to 0 until their pre-registered ICs pass; a descriptive rank built half from unvalidated categories misleads more than it informs.
- **Any use of allocation-engine sizing with real capital** — uncalibrated by its own definition.
- **Conviction grades on congressional clusters** — delayed, committee-blind, unvalidated; the label would not survive compliance.
- (Not killed: Futures 15m tab — it's an execution monitor for the user's manual trading, and the platform already recorded the honest negative result on intraday signals.)

## C. Keep list (strong enough today)
- RSI(2) research result + its replication harness (as a paper-trade candidate).
- The validation pipeline itself: pre-registration, both-windows gate, permutation/bootstrap, negative-results log — this is the most institutional thing in the system.
- Data-integrity engineering: point-in-time snapshots, delay disclosure, stale-not-fabricated quotes, error-payload cache exclusion.
- Alerting, portfolio accounting, decision journal design.
- AI layer boundaries (grounded, read-only, degradation verified).

## D. Next 3 highest-value fixes (risk reduction ÷ effort)
1. **Move prediction/scores/state logging into a background daily loop** (not
   request-driven). ~20 lines. Unblocks calibration — the single number that
   decides whether anything here may ever touch capital.
   **[EXECUTED 2026-07-05 — `research_log_loop`, 4x/day, date-deduped.]**
2. **Verify FOMC_DECISIONS against the Fed's published calendar** (one-time
   script or manual check; record verification date in the code comment).
   Protects the only measured event study from silent corruption.
   **[EXECUTED 2026-07-05 — 44/44 dates 2021–2026 match official statement
   links; 2019–2020 match historical pages; recorded in code.]**
3. **Add a stdlib smoke-test script** (import quanta with FORCE_SYNTH, call
   every view, assert schema + no exception; run in Docker build). First
   automated regression net for 7k lines. ~1–2 hours.
   **[EXECUTED 2026-07-05 — smoketest.py, 30 views + invariants, Docker
   build gate.]**

---

## Final classification
**Decision-support tool** — above a research prototype (it has falsification
discipline, negative-results memory, point-in-time data engineering, and it
audits itself), below a production investment system (zero live track record,
uncalibrated probabilities, unvalidated composite components, no automated
tests, single-user architecture). The honest path to "production-grade" runs
through: Fix #1 → 30+ matured predictions → calibration verdict → paper-trade
RSI(2) through the decision journal → quarterly re-verification — not through
any new feature. That is exactly what the Research Director's backlog already
says, which is the system working as designed.
