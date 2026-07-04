# Roadmap (standalone platform)

Ordered by expected impact. Items graduate through the Model Registry stages;
several are **data-gated** and activate automatically as history accumulates.

1. **Longer daily history** (one-time 10y import or paid tier) — the binding
   constraint on every engine; the aligned-matrix code is source-agnostic.
2. **Options-category IC test** — auto-unblocks at ~60 snapshot days
   (`options_history.json` accrues daily; PCR-z live at ≥20 days).
3. **GEX/DEX-change predictiveness** — snapshots now store netGEX/netDEX;
   test in `research_categories.py` style once history exists.
4. **Inverted-volatility (high-beta) category** — pre-registered 2026-07-03;
   evaluate on data unseen at registration only.
5. **IV-rank filter on RSI(2) entries** — variant in research.py once IV history exists.
6. **Regime/entry-context expectancy for the user's own trades** — journal is
   tagging entries (regime, RS group, breadth, vol pctile); analysis becomes
   meaningful at n≥10 closed trades per group.
7. **Adaptive weighting** — verdict auto-flips when a regime bucket reaches
   n≥30 weekly ICs (test already runs continuously).
8. **Analog-engine feature weighting** — needs >100 weeks; equal weights until then.
9. **Regime-boundary validation** — classifier thresholds are conventional;
   validate like the categories once sample allows.
10. **Edge-lab survivor re-verification** — survivors are watchlist candidates;
    re-run each quarter, promote only what keeps surviving on new data.

Superseded: the original k8s/Go/Next.js stack (still in repo root) — the
standalone Python platform is the product.
