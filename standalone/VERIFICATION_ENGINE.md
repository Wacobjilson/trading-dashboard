# Verification Engine

`verify_view()` → `/api/verify` → Trust dashboard (Research tab). Runs live on
every call; results cached 120s. Also run in the Docker build smoke test.

## Checks (each: pass/fail, severity, human-readable detail, category)
| # | Check | Severity | Method |
|---|---|---|---|
| 1 | no synthetic bars in production | critical | `_bars_meta[sym].source` for SPY+sectors |
| 2 | data mode | critical/info | `_demo_mode()` (polygon key + FORCE_SYNTH) |
| 3 | SPY/XLK price agreement across stores | high | bars vs live-quote vs ODE store, ≤3% spread |
| 4 | RSI(2) cross-implementation agreement | high | `rsi()` vs `_rsi_ser()` per sector, ≤0.5 |
| 5 | no NaN/Inf in payloads | high | recursive scan of scores/regime/ode/gov/director |
| 6 | scores within [0,100] | medium | bounds on sector composite |
| 7 | daily bars fresh (<4d) | medium | data-quality report bar age |
| 8 | live quotes fresh (<10m) | low | data-quality report quote age |
| 9 | no dead worker threads | critical | `_hb[*].dead` |
| 10 | no provider >50% error rate | high | per-host error/call from ops |
| 11 | AI safety preamble enforces grounding | high | assert phrasing in `AI_SAFETY` |
| 12 | confident agent findings cite evidence | medium | last cycle: conf≥40 ⇒ supportingEvidence |

## Trust score
Pass-weighted by severity (critical 5 / high 3 / medium 2 / low 1). **Any
critical failure forces trust = 0** regardless of the rest. `verdict` states
plainly whether a critical defect blocks trust.

## Worker liveness
`_hb_wrap` wraps every loop thread; it records start, and if the loop function
ever returns or raises, marks the worker `dead` with the exception. The
verifier fails critically on any dead worker. Per-feed staleness is covered
separately by the data-quality report (bar/quote/congress ages).

## Extending
Add a `chk(name, ok, severity, detail, category)` call inside `verify_view()`.
Keep checks cheap (they run on a 120s cache) and prefer independent
recomputation over trusting a stored value.

## Limitation
Checks run against cached production state, not a frozen fixture — a check
that needs an external provider (cross-provider price) is done manually in the
audit (SYSTEM_AUDIT.md) rather than on every call, to avoid rate-limit load.
