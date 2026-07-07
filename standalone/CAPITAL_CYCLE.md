# Capital Cycle — AI (Phase 22)

A self-contained module (namespace `cc_` / `CC_` in quanta.py) that reframes
part of the platform around the **industry capital cycle** (Marathon Asset
Management / Edward Chancellor, *Capital Returns*) — specialized to detect when
the **AI capex/equity boom is topping**.

## The framework
Supply-side mean reversion: high returns → capital floods in → capex/capacity
build-out → supply overshoots → returns fall → capital withdraws → scarcity
restores pricing power → repeat. **Bubbles top at step 2→3**: capital and
capacity still surging while the *marginal return on that capital* quietly
deteriorates. The module's core job is measuring that **widening gap between
capital committed and returns realized** for the AI complex (semis,
hyperscalers, data-center/power, AI software). The tell of a top is **maximum
capital commitment + peak narrative + deteriorating incremental economics —
not price.**

## Config-driven (`CC_CONFIG`)
Basket (hyperscalers/semis/AI-software), capex leaders, circular-financing
entity list, all thresholds, and composite weights live in one dict. Tune
without touching logic. The **capex-up-while-returns-down divergence is
weighted most (0.30)** — that specific combination separates a real top from
healthy expansion.

## Panels (each indicator: value + raw series + timestamp + source; degrades to "no data")
1. **Supply / capex** — aggregate AI-leader capex ($B), YoY, capex/revenue (FMP).
2. **Returns / monetization** — mean ROIC, gross-margin trend/direction (FMP).
   Rising GPU depreciation compressing margins = late-cycle tell.
3. **Valuation** — basket EV/Sales with percentile vs **own accumulated
   history**, real 10y yield (FRED) as the ERP bar.
4. **Behavioral / sentiment** — AI-basket news sentiment (Alpha Vantage
   NEWS_SENTIMENT, 25 req/day → slow rotation), "AI bubble" article-volume
   percentile (GDELT, keyless).
5. **Circular / vendor financing** (prominent) — SEC EDGAR full-text search
   over 180d of filings for AI strategic-investment / vendor-financing language
   and counterparty co-mentions (NVIDIA/CoreWeave/OpenAI/Oracle…). The dotcom
   Lucent/Nortel tell. A screen for review, not a confirmed finding.
6. **Credit & liquidity** — HY OAS (FRED) widening off its 6-mo low = early
   crack. (Issuer-level DC-bond spreads are paid; HY aggregate is the free proxy.)
7. **Breadth / concentration** — AI-basket breadth (% > 50-DMA) and top-name
   concentration of the up-move (Polygon grouped-daily, via the ODE store).
8. **Physical bottlenecks — power** — US electricity demand YoY (EIA-930) as a
   data-center-draw proxy. GPU lead times / cloud utilization have no feed → no-data.
9. **Capital raising** — AI-tagged ATM/S-1 issuance count (EDGAR full-text proxy).

## Composite four-phase model
`Abundance / Peak Supply` → `Contraction` → `Trough / Scarcity` →
`Recovery / Expansion`. A 0–100 risk score (weighted contributions, shown
per factor) plus the phase label. Phase logic keys off the divergence:
`surging AND deteriorating` ⇒ peak-supply/top-risk; add a credit/breadth crack
⇒ Contraction (the "it's popping" flip).

## Signals (discrete, staged, timestamped)
Capex-Return Divergence · Circular-Financing Alert · Euphoria Trigger · Breadth
Break · Credit Crack · Rollover Confirmation — each **Watch → Warning →
Trigger**, showing the exact conditions + contributing series, fired through
the standard alert engine (`_check_cc_alerts`, kind `capcycle`).

## Replay
`/api/capital_cycle/replay` runs the credit-crack mechanic over available free
history (FRED HY OAS = years) to sanity-check behavior into past stress
(2018Q4, 2020, 2022). Honest: validates the mechanic, **not** a tradable
backtest; fundamental-divergence history is limited by FMP free-tier depth.

## Data honesty (guardrails)
No false precision, no overfitting to one past bubble. Every score drills to
its inputs. Explicit "no data" for: VC/PE deal flow, issuer-level DC credit
spreads, GPU lead times / cloud utilization, quality forward consensus — no
credible free feed, shown as no-data, never estimated. Labeled decision-support,
not an oracle; it does not claim to time the top.

## Rate budgets (`cc_loop`, 12h)
FMP fundamentals 6-day cache; Alpha Vantage capped at ~4 names/cycle (25/day
free limit); EIA/FRED/GDELT/EDGAR generous. Valuation & ROIC snapshot daily to
accumulate the percentile history.

## Integration points (only these touch existing code)
New tab "Capital Cycle"; `/api/capital_cycle` + `/api/capital_cycle/replay`;
`_check_cc_alerts` in the alert sweep; `cc_loop` thread; keys in `.env`
(`ALPHAVANTAGE_API_KEY`, `EIA_API_KEY`). No existing view modified.
