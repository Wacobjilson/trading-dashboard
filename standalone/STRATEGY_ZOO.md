# Strategy Zoo (Phase 20)

A registry of deliberately **orthogonal** strategy families — different
economic mechanisms so their edges are uncorrelated. **Hard admission rule:
every family must declare its economic rationale AND who is on the other side
of the trade.** No rationale, no admission — the strategy-level equivalent of
Phase 18's "if a number appears, you can prove where it came from."

## Testable families (run through the full gate over deep history)
| Family | Mechanism | Who's on the other side |
|---|---|---|
| **RSI(2) mean reversion** | oversold liquid ETFs in an uptrend bounce as forced sellers exhaust | panic/stop-loss/margin sellers and mechanical index rebalancing |
| **Momentum** | under-reaction + slow capital reallocation lets trends persist | early value sellers, disposition-effect profit-takers |
| **Trend-less deep mean reversion** | sharp drops below a short MA may over-shoot — *no trend filter* | momentum sellers — but may just be catching falling knives (gate should reveal) |
| **High-breakout continuation** | new highs = resolved uncertainty, fresh demand | range-faders — historically the fade won on ETFs (EXP-01) |

The last two are included *expecting* rejection — a gate that only admits
winners is broken. Re-rejecting a plausible idea on fresh data is a success.

## Untestable families (declared, honestly not backtestable on the free tier)
| Family | Rationale | Why untestable |
|---|---|---|
| Deep-value fundamental | market over-extrapolates temporary bad news on quality | no point-in-time historical fundamentals → tracked FORWARD-ONLY (Phase 19) |
| Post-earnings drift | investors under-react to surprises | no free historical earnings-date+surprise dataset at scale |
| Dealer-flow / GEX | dealer gamma hedging amplifies/dampens moves | GEX sign is the unverifiable +call/−put assumption (Z-04); no chain history |

These carry edge confidence 0 and status `untestable` — the engine states the
data gap instead of manufacturing a backtest.

## Adding a family
Add a dict entry to `STRATEGY_ZOO` with a backtest generator `fn(m, cost) →
trades[{sym,i,exit_i,date,ret}]`, a `rationale`, and an `otherSide`. It is
picked up by the gate, the trial count, the regime router, and verification
automatically. New economic mechanisms (carry, seasonality, credit) are the
right additions — not more parameterizations of momentum.
