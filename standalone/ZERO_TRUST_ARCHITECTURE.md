# Zero-Trust Architecture

**Principle: nothing is assumed correct; everything must continuously prove it
is correct.** Every subsystem is treated as defective until a live check says
otherwise. This is separate from the research-validation gates: those prove an
*edge* exists; zero-trust proves the *software is not lying about numbers*.

## Layers of proof
1. **Provenance** — every displayed number traces to a source (DATA_PROVENANCE.md).
   Bars carry `source` (polygon|synth|deep); quotes carry provider; the
   verifier fails critically if synthetic bars serve in production mode.
2. **Self-consistency** — the same symbol's price must agree across the bar
   cache, live-quote store, and the ODE market store (tolerance 3%).
3. **Independent recomputation** — key calculations are computed twice by
   separate code paths and compared (e.g. RSI(2) via `rsi()` vs `_rsi_ser()`);
   disagreement is reported, never silently resolved.
4. **Bounds & corruption** — scores ∈ [0,100], probabilities ∈ [0,1], and a
   recursive NaN/Inf scan over payloads.
5. **Freshness** — feed ages within tolerance (bars <4d, quotes <10m).
6. **Worker liveness** — every background loop is wrapped so a dead thread is
   detected (`_hb`), not silently lost.
7. **AI grounding** — the safety preamble is asserted present; confident agent
   findings must carry cited evidence (AI_TRUTH in SYSTEM_AUDIT.md).

## Enforcement
`verify_view()` (`/api/verify`, Trust dashboard on the Research tab) runs all
checks live on every call (120s cache). A **critical failure forces trust=0**.
The `verify_view` is also exercised by the Docker build smoke test, so a change
that breaks a core invariant cannot ship.

## What zero-trust does NOT claim
It does not prove the models make money, that thresholds are optimal, or that
approximations (GEX dealer convention, curated sector maps) are right — those
are documented in KNOWN_ISSUES.md and the Institutional Readiness Assessment.
It proves the plumbing is honest.
