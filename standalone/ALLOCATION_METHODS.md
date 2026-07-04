# Position Sizing Methods

`/api/sizing?symbol=&equity=&risk=` computes every method side-by-side.
**No method is crowned** — each has a failure mode, listed with its output.

| Method | Formula (as implemented) | Pro | Con |
|---|---|---|---|
| Fixed risk | risk$ ÷ (entry − structure stop) from the entries scanner | Uniform loss per stop-out | Stop distance drives share count; ignores vol clustering |
| ATR risk | risk$ ÷ 2×ATR(14) | Adapts to current volatility | ATR lags regime shifts |
| Vol targeting | 15% target ÷ sector ann vol → % of equity | Stabilizes portfolio variance | Targets vol, not loss; implies leverage when vol is low |
| ¼-Kelly | f* = (p − (1−p)/b)/4, p and payoff b from the probability engine's 10d base rates (n shown) | Growth-optimal direction | Inputs are 2yr base rates — full Kelly on noisy inputs overbets catastrophically, hence ¼ only |
| Equal risk contribution | equalize daily-vol contribution across open positions | No position dominates risk | Ignores conviction differences |
| Portfolio heat | (open positions + 1) × risk% vs a 6% desk cap | Caps aggregate loss potential | Blunt; ignores correlation between positions |

## Scenario simulator (`/api/simulate`)

Impact = Σ weight × 63d univariate factor beta × factor shock, per scenario
(rate spike, vol spike, oil shock/collapse, dollar spike, tech correction,
credit stress, COVID-style). **Linear approximation** — real crises are
non-linear and correlations spike; the payload carries this caveat. Portfolio
stats (β, vol, 1y maxDD, worst day) replay the last ~252 sessions of the given
weight mix. Works on current positions or the suggested allocation
(`?w=XLK:20,XLF:10` for arbitrary books).
