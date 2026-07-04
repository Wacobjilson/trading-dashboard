# Factor Library

Factors available to the Factor Intelligence Engine (`factors_view` in quanta.py).
All are **liquid-ETF proxies or series derived from our own bars** — free-tier
honest. No free source exists for real yields, CPI/PPI surprise series, ISM,
retail sales, MOVE, or credit-spread indices; those families are represented by
the closest proxy or absent, never fabricated.

| Factor id | Represents | Construction | Family |
|---|---|---|---|
| TLT | Long-end rates (up = yields down) | ETF closes | Interest rates |
| UUP | US dollar | ETF closes | Currencies |
| USO | Crude oil | ETF closes | Energy |
| GLD | Gold / real-yield & hedge demand | ETF closes | Inflation/risk |
| CPER | Copper / global growth impulse | ETF closes | Growth |
| VIXY | Volatility regime | ETF closes (VIX futures proxy, decays) | Volatility |
| HYG | High-yield credit / risk appetite | ETF closes | Risk appetite |
| RSPvSPY | Equal-weight vs cap-weight participation | RSP ÷ SPY | Market structure |
| IWMvSPY | Small vs large caps | IWM ÷ SPY | Market structure |
| QQQvSPY | Growth / mega-cap-tech leadership | QQQ ÷ SPY | Market structure |

Derived market-state features (weekly, used by regime/analog/edge engines):
breadth (% sectors > 50-day SMA), realized-vol percentile, cyclical−defensive
1m RS spread, EW−SPY 1m, average pairwise sector correlation (21d).

Options-structure factors (GEX, DEX, IV, skew, gamma flip, OI migration) exist
as **current values + accumulating daily snapshots** (`options_history.json`);
they join the time-series factor set automatically once enough days exist.

## Method notes

- Attribution is **univariate**: per factor, β over 63d daily returns × the
  factor's 21d move. Factors overlap → contributions don't sum; the residual is
  displayed.
- Stability: ρ(last 63d) vs ρ(prior 63d); |Δρ| ≥ 0.4 raises an automatic
  relationship-break flag.
- Persistence: P(21d factor trend keeps its sign for another 21d), estimated on
  weekly samples with n shown; suppressed when n < 20.

## Adding a factor

One line in `FACTOR_DEFS` (plus `MACRO_PROXIES` if it needs bars warmed, and
`FACTOR_RATIOS` if it's a ratio). The engine picks it up everywhere.
