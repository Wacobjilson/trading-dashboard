# Trust Framework

How the platform earns and displays trust, and what each trust signal means.

## Two independent trust systems (do not conflate them)
1. **Software correctness** — the Verification Engine (`/api/verify`). Proves
   numbers are sourced, consistent, reproducible, in-bounds, fresh, and that
   workers are alive. A critical failure ⇒ trust 0.
2. **Research validity** — the validation pipeline (EXPERIMENT_LOG, registry,
   calibration). Proves a claimed edge survives out-of-sample testing.
   Separate gate; a correct number can still describe a rejected edge (the
   composite score is correct AND descriptive-only).

## Trust dashboard metrics (Research tab)
| Metric | Meaning |
|---|---|
| Trust score /100 | severity-weighted pass rate; 0 if any critical fails |
| Pass rate | checks passing / total |
| By-category | provenance / consistency / calculation / freshness / workers / providers / ai |
| Critical defects | must be empty for any trust > 0 |
| Workers | heartbeat/dead state per background loop |

## Classification vocabulary (used in the Readiness Assessment)
- **Production Ready** — correct, reproducible, and either validated or purely
  mechanical (accounting/plumbing).
- **Conditionally Production Ready** — correct but depends on an unvalidated
  assumption or unmatured gate; usable as context, not for sizing.
- **Research Only** — descriptive/exploratory; correct numbers, no proven edge.
- **Experimental** — data or validation immature.
- **Untrusted** — assumption-rooted or unverifiable; never size capital on it.

## The standard
> If a number appears in the app, you can prove where it came from, reproduce
> it independently, and explain why to trust it.

Met for: prices, RSI(2), scores, probabilities, fundamentals-from-FMP,
filings-from-EDGAR. Explicitly NOT met (and labeled) for: GEX dealer
positioning, any FMP-computed ratio not yet reproduced from XBRL.
