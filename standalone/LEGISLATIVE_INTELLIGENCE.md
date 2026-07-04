# Legislative & Regulatory Intelligence — pipeline reference

## Regulatory feed (`fetch_fedreg` → `/api/congress_reg`)
- **Source:** Federal Register API (official, keyless). 40 newest documents
  across 13 market-relevant agencies: SEC, Federal Reserve, OCC, EPA, DoE,
  FDA, HHS, FTC, DOJ, FCC, DoD, DOT, USDA.
- **Sector mapping:** curated agency→sector table (e.g. FDA→XLV, EPA→XLE/XLB/
  XLU, DoD→XLI) — an analytic judgment, labeled as such, not official data.
- **Significance:** "Rule"/"Proposed Rule" flagged over routine notices.
  Publication in the Register ≠ market impact; this feed answers "which
  agencies are active on which sectors", not "what will move prices".

## Political calendar (`political_calendar`)
- FOMC 2026 meeting dates (Federal Reserve published schedule, static list).
- Upcoming Treasury auctions (FiscalData API, official, keyless).
- High-impact economic releases (existing calendar feed).
- **Bills / hearings / markups / votes:** require the free congress.gov API
  key (https://api.congress.gov/sign-up) — the calendar states this until
  `CONGRESS_GOV_API_KEY` is set. Committee rosters have no free API at all;
  committee intelligence is limited accordingly and says so.

## Known gaps (stated, not papered over)
FDA approval calendars (PDUFA dates), lobbying intensity (Senate LDA API
exists but client-name matching to tickers is unreliable — parked), DoD
contract-award-to-ticker mapping (USAspending recipient names are fuzzy —
parked), election milestones. Each would enter DATA_SOURCES.md with its
limitations if added.
