# Known Issues (zero-trust register)

Each: description · severity · evidence · root cause · affected · risk · fix ·
verification · regression test. Open items are the honest defect backlog.

## RESOLVED

### Z-01 · Futures source label could lie (HIGH) — FIXED Phase 18
- **Description:** `futures_state` labeled `source:"polygon"` whenever the key
  existed, but `fetch_intraday` silently falls back to synthetic bars on fetch
  error — so synthetic intraday bars could be presented as "polygon".
- **Evidence:** code review of the fallback path (fetch_intraday except → synth).
- **Root cause:** source label derived from config, not the actual fetch outcome.
- **Fix:** `_intraday_src[proxy]` records the TRUE source; label reads it; the
  fetch failure now also increments an ops error counter.
- **Verification:** futures payload `source` now flips to `synth` on fetch fail.
- **Regression test:** smoke test exercises futures_state; ops error visible.

### Z-02 · Mock quotes merged into real charts (CRITICAL) — FIXED Phase 15
The "giant red bar": failed live-quote fetches were replaced by a random walk
seeded from stale prices and merged into real candles. Fixed (stale-not-
fabricated + verify check #1 guards against synth-in-production).

### Z-03 · Demand-driven prediction logging (HIGH) — FIXED Phase 15
Calibration data only logged when a tab opened. Fixed with `research_log_loop`.

## OPEN

### Z-04 · GEX dealer convention is an assumption (HIGH — inherent)
- **Evidence:** naive +call/−put; real dealer inventory unobservable free.
- **Risk:** GEX flip/wall levels can mislead exactly when they matter.
- **Mitigation:** stated on every options payload; verify does not bless it;
  MIOS options agent repeats the limitation. **Not fixable without paid data.**

### Z-05 · No independent reproduction of FMP TTM ratios (MEDIUM)
- **Evidence:** deep-value ratios come from FMP's computation, not rebuilt from
  SEC XBRL raw statements.
- **Risk:** a provider error propagates into deep-value scores.
- **Fix (planned):** reconstruct 2–3 key ratios from EDGAR companyconcept and
  add a verify cross-check (like RSI #4).

### Z-06 · Single Polygon key / single-process scale ceiling (MEDIUM)
- **Evidence:** STRESS_TEST.md — fine at 1 user, fails at 100.
- **Risk:** none for the single-user design; documented so scope is explicit.

### Z-07 · Earnings-call & 13F data absent (LOW — honest gap)
- Deep-value engine has no transcript/13F source on the free tier; the
  corresponding "agents" are described but the data is marked absent, not
  approximated.

### Z-08 · Ops/verify counters reset on restart (LOW)
- Heartbeats and error counters are process-lifetime; a restart clears history.
  Acceptable for a personal deployment; noted for honesty.

### Z-09 · Deep-value leverage penalty not sector-adjusted (MEDIUM)
- **Evidence:** live scan flagged JPM as a value-trap (financial strength 0)
  purely on D/E 3.39 — but banks structurally carry high leverage.
- **Root cause:** `financialStrength` applies a flat D/E penalty across sectors.
- **Risk:** financials/REITs/utilities systematically mis-scored on strength
  and over-flagged as traps.
- **Fix (planned):** sector-relative leverage percentiles instead of an
  absolute D/E threshold. Until then the raw metrics are shown so the user can
  see *why* — the flag is transparent, not silent.

### Z-09 UPDATE · Sector-adjusted leverage — FIXED Phase 20
Deep-value `financialStrength` now penalizes D/E on the *sector percentile*
(`de_by_sector` pools), not an absolute threshold. Live check: GS (D/E 6.1) no
longer auto-flagged as anomalous within Financial Services. Percentiles sharpen
as rotation coverage fills the sector pools.

### Z-11 · Regime-detection uncertainty not quantified (MEDIUM — new, Phase 20)
- **Evidence:** the Regime Router surfaces a regime + a qualitative caveat, but
  the router's edge matching treats the current regime label as certain.
- **Risk:** an edge shown as "active in this regime" inherits the (unstated)
  probability that the regime label is wrong.
- **Fix (planned):** propagate `regime.confidence` into the router's per-edge
  confidence, and widen the "no validated edge" default when regime confidence
  is low. Router already states the caveat in prose.

### Z-10 · RTY/YM intraday falls back to synthetic (LOW — now visible)
- **Evidence:** post-Z-01, futures payload shows ES/NQ `polygon` but RTY/YM
  `synth` — Polygon free tier returns no 15-min data for the IWM/DIA proxies.
- **Root cause:** provider coverage/rate limit on those symbols.
- **Risk:** low — the Futures tab is labeled context-only (EXP-02: no intraday
  edge) and the source now honestly reads `synth`. Previously this was HIDDEN
  behind a false "polygon" label (Z-01). Investigate whether a different proxy
  or the daily-resample path should feed these two.
