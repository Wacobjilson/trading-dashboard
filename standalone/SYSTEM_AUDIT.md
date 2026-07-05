# System Audit — Phase 18 (evidence log)

Independent verification performed 2026-07-05 against the live deployment.
Method: attempt to break each subsystem; record evidence.

## Endpoint sweep
All 37 GET endpoints return HTTP 200 with no `error` field (script sweep).
`/api/verify` runs 14 live checks: **14/14 pass, trust score 100/100, 13
workers alive, 0 dead**.

## Cross-provider price verification (independent reproduction)
SPY daily close, three independent sources:
- Polygon (platform bars) 2026-07-01 = **745.76**
- Yahoo v8 (independent) = **745.76** → diff **0.000%**
- Finnhub live last vs chart forming bar = **0.00%**
Deep history (Yahoo) verified within 0.52% of Polygon overlap (prior).

## Calculation cross-check
RSI(2) computed by two independent implementations (`rsi()` Wilder path vs
`_rsi_ser()` series) — agree on all 11 sectors within 0.5 (verify check #4).
Reverse-DCF is bisection on a transparent PV model; inputs shown.

## Demo / placeholder detection
Grep of every `synth`/`mock`/`SEED_PRICES` path: all gated behind
`FORCE_SYNTH or not API_KEYS.get("polygon")` (demo-only) EXCEPT the two defects
found and fixed/logged:
- **Z-01 (FIXED):** futures could label synthetic intraday bars as "polygon".
  Fix verified — RTY/YM now honestly read `synth` (Z-10), ES/NQ read `polygon`.
- **Z-02 (FIXED Phase 15):** mock quotes into real charts. Verify check #1 now
  guards against synth-in-production critically.
No hardcoded prices/scores/fixtures reachable in production paths.

## Self-consistency
SPY and XLK prices agree across the bar cache, live-quote store, and ODE market
store within tolerance (verify check #3). No divergent same-symbol values found.

## Worker verification
13 background loops wrapped with heartbeats; a thread that returns or raises is
marked `dead` and fails verification critically. All alive at audit. Per-feed
freshness (bars/quotes/congress) tracked separately in ops.

## Deep-value engine (Phase 19) live proof
Fetched real FMP fundamentals for JPM/XOM/PFE/KO/INTC; scoring produced
evidence-based, differentiated results (PFE surfaced on quality+value+strength
agreement; JPM/XOM value-trap-flagged on weak balance sheet). Confirmed the
agreement gate and value-trap guard work. Limitation Z-09 (leverage not
sector-adjusted) found and logged.

## Static review highlights
- 6 broad `except: pass`/`except Exception` sites — all in loop bodies or
  best-effort persistence, now routed through `_ops_err` where they matter
  (visible in ops, not silent).
- Single-file, ~7,400 lines, 0 external deps — deliberate; smoke test (35
  views) is the regression net and runs in the Docker build.
- No auth/secrets in code (verified key-scan on every commit); keys in
  gitignored `.env` only.

## Not independently reproduced (honest gaps)
- GEX dealer positioning (assumption, unverifiable free) — Z-04.
- FMP TTM ratios not rebuilt from SEC XBRL — Z-05.
- Options chains: single provider (CBOE), no cross-check available free.
