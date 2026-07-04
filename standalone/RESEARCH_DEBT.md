# Research Debt Register

What limits the platform's accuracy right now, ranked. Live version:
`/api/priorities` (unblock %s computed from actual data counts).

| # | Debt | Blocks | Expected improvement | Effort | Status |
|---|---|---|---|---|---|
| 1 | ~~2yr history ceiling~~ | every research engine | HIGH | low | **PAID 2026-07-04** — Yahoo deep history (~8y common window; 25y for pre-XLC sectors available to future per-sector studies) |
| 2 | Options time-series (60d) | options-category IC, GEX-change research, IV-rank filter | MED-HIGH | none (accruing daily) | ~2/60 days |
| 3 | Matured predictions (30) | confidence calibration, forecast post-mortems | MED | none (accruing 11/day) | maturing |
| 4 | Journal closed trades (≥10/group) | personal expectancy, decision-vs-luck analytics | MED | none (user-paced) | collecting |
| 5 | Constituent-level breadth | true A/D, NH/NL, % stocks above MAs | MED | HIGH (needs ~500-symbol feed) | no free source — sector-level proxy in use |
| 6 | Real macro series (yields, CPI surprises, ISM, credit spreads) | factor library fidelity | MED | MED (paid source) | ETF proxies in use, labeled |
| 7 | Intraday futures data (real ES/NQ) | futures tab beyond context | LOW-MED (EXP-02 says no edge anyway) | HIGH (paid) | parked |
| 8 | Dealer inventory / flows / blocks | options intelligence completeness | UNKNOWN | not purchasable at retail | permanently marked unavailable |

Rule: debt items enter `/api/priorities` so the platform itself re-ranks them
as data accrues; an item is retired here only with the evidence that paid it.
