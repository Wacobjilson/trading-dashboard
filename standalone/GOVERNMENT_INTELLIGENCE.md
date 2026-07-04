# Government & Policy Intelligence Center — pipeline reference

The **Government** tab (formerly Congress) is the single destination for
congressional trading, legislation, regulation, political calendars, sector
policy exposure, company government profiles, catalysts and government
research. Everything on it is **descriptive context**: no government signal
enters the composite score, probability engine or allocation gate until it
passes the same pre-registered validation as every other model
(MODEL_REGISTRY.md rules; see DISCLOSURE_LIMITATIONS.md for the trades
caveats, CONGRESSIONAL_DATA.md for the trades pipeline).

## Legislative intelligence (`fetch_bills` → `/api/government`)
- **Source:** congress.gov v3 API (official, free key). 20 most recently
  updated bills: number, title, origin chamber, latest action + date,
  congress.gov link.
- **Policy classification:** keyword rules (`POLICY_AREAS`) route titles to
  areas (Antitrust, Drug approvals, Energy, Defense, Banking, AI, Telecom,
  Trade/tariffs, Sanctions/export controls, Tax, Environment) and areas to
  sectors (`POLICY_SECTOR`). Labeled keyword-based; read the bill.
- **Deliberately absent:** passage probabilities and market-impact estimates —
  no validated model for either; showing numbers would be false precision.
- Amendments, hearings/markups, votes and committee rosters have no adequate
  free machine-readable source at useful latency; the tab says so rather
  than approximating.

## Regulatory intelligence (`fetch_fedreg` → `/api/congress_reg`)
- Federal Register API (official, keyless), 40 newest documents across 13
  market-relevant agencies; agency→sector curated map; Rule/Proposed Rule
  flagged over routine notices; policy-area badge from the same classifier.
- Publication ≠ market impact: this answers "which agencies are active on
  which sectors", not "what will move prices".

## Political calendar (`political_calendar`)
FOMC 2026 dates (published schedule), Treasury auctions (FiscalData,
official), high-impact economic releases, latest bill actions. Each item
carries its source. No "historical market reaction" column — that requires a
validated event study, which is registered future research, not a display
default.

## Sector government exposure (`SECTOR_GOV_EXPOSURE` → `/api/government`)
Curated 0–3 structural ratings per SPDR sector across 8 dimensions (gov
spending, defense, health policy, regulation, trade/tariffs, rates, fiscal,
election), each with a written rationale. These are **analyst judgments,
labeled as such** — not measured coefficients. The LIVE columns (Federal
Register docs 90d, congressional buys/sells 90d, active mapped bills) are
measured counts. Rates sensitivity is the one dimension with independent
measured support (factor library fredRealY10/fredCurve betas).

## Catalyst dashboard
One dated, filterable list merged from: FOMC/auctions/economic releases,
bill actions, Federal Register rules, and high-conviction congressional
cluster buys. Priority is a display heuristic (scheduled Fed events >
legislation/rules > delayed filings), not an impact estimate. Every row
shows source and confidence basis.

## Company government profile / knowledge-graph lite
For the 40 most-disclosed tickers: mapped sector, members who filed trades,
regulators active on the sector, recent bills mapped to the sector. Links
are **sector-level, not company-verified** — committee memberships, contract
awards and investigations have no free machine-readable source, and the
panel says so. Click any ticker on the tab to open its profile.

## Government research (`/api/government` → pipeline)
- **EXP-13** (pre-registered 2026-07-04, EXPERIMENT_LOG.md): follow-the-filing
  — entry at DISCLOSURE close, 90d hold, excess vs SPY. Gate: n≥40 matured,
  Wilson CI excl. 50%, mean>0, then OOS replication on new disclosures.
  Live readout on the tab; recorded prior expectation: FAIL.
- **GOV-02:** sector net congressional buying vs forward sector-relative
  returns — gated on ≥26 weekly heat observations (daily snapshots persist
  in congress_trades.json → heatHistory, started 2026-07-04).
- **GOV-03:** Federal Register rule-count spikes vs sector vol/returns —
  same snapshot store.

## Known gaps (stated, not papered over)
FDA approval calendars (PDUFA), lobbying intensity (Senate LDA client-name→
ticker matching unreliable — parked), DoD contract-award→ticker mapping
(USAspending recipient names fuzzy — parked), election milestones, committee
rosters, FMP House disclosures (402 premium-gated on free tier; Senate
flows). Each would enter DATA_SOURCES.md with its limitations if added.
