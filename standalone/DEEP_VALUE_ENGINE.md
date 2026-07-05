# Deep Value Research Engine (Phase 19)

Continuous fundamental research — not a cheap-multiple screen. Forms a living
thesis per company, requires independent evidence to agree before surfacing,
and has an AI reviewer attack every thesis.

## Data sources (real, honest gaps stated)
- **FMP stable API** (free tier, works): `profile` (price/mktcap/sector/beta),
  `key-metrics-ttm` (EV, FCF yield, ROIC, EV/EBITDA), `ratios-ttm` (margins,
  P/E, P/B, current ratio, D/E, interest coverage). 3 calls/name.
- **SEC EDGAR** (official, keyless): `company_tickers.json` (ticker→CIK once),
  `submissions/CIK.json` (10-K/10-Q/8-K/restatement detection with accession
  provenance). The filing agent quotes real filing metadata.
- **Absent, not estimated:** earnings-call transcripts (FMP premium), 13F
  institutional ownership (limited free), analyst revisions. Marked absent.

## Rate discipline
FMP free ≈ 250 req/day. `deepvalue_loop` refreshes the least-recently-fetched
names within `DV_FMP_DAILY_CAP` (default 60 → 20 names/day), 6-day cache
(fundamentals change quarterly). Coverage % is displayed — "thousands" would be
dishonest on this budget; the universe is the curated ~90 large/mid-caps +
watchlist.

## Scoring (transparent; agreement gates confidence)
Sub-scores 0–100: **quality** (ROIC + operating/gross margin, no single metric
dominates), **valuation** (FCF-yield & EV/EBITDA *percentile vs peers*),
**financial strength** (current ratio, D/E, interest coverage),
**capitalAllocation** (payout sustainability). Composite = 0.25·quality +
0.30·valuation + 0.20·strength + 0.10·capAlloc + 0.15·agreement.
**Confidence rises only when quality + valuation + strength independently
agree**; a cheap-but-fragile name lowers confidence and raises an explicit
**value-trap flag** — conflicting evidence is never averaged away.

## Reverse DCF (no forecasts invented)
Solves for the FCF growth rate that makes PV(FCF) = enterprise value — i.e.
**what the market is assuming**, framed as margin of safety ("prices in ~X%
growth; lower true growth = upside"). Honest because it forecasts nothing.

## Living thesis + AI
Per-company thesis persists (`deepvalue.json`): first-researched price, score
drift (strengthening/weakening), return path (MFE/MAE). Two AI modes:
`deepvalue` (institutional research note — must cite the specific fundamentals/
filing, never says buy) and `thesis-challenge` (adversarial value-trap review).

## Learning
Matured theses (30d+) are split by surfacing score; forward returns compared
(gate 10). Grades whether a higher deep-value score predicted better outcomes —
not a backtest (no entries/costs), and any edge claim still needs the
pre-registered pipeline.

## Zero-trust posture
Every displayed number traces to FMP or an SEC filing. FMP-computed ratios are
not yet independently reproduced from XBRL (KNOWN_ISSUES Z-05). Deep-value
candidates are research, never recommendations.
