# Disclosure Limitations — read this before using the Congress tab

## The delay is structural, not a bug
The STOCK Act requires members of Congress to disclose trades within **45 days**
of the transaction (many file later; enforcement is weak). By the time a trade
appears anywhere — this platform, paid services, news — the member has held the
position for weeks. **No product has real-time congressional trades.** Anyone
implying otherwise is selling false precision.

Every record in this platform therefore displays: trade date, disclosure date,
the computed delay (flagged red when > 45 days), source, collection timestamp,
and verification status ("as filed — unverified").

## Amounts are ranges, not values
Disclosures use bands ($1,001–$15,000 … $5,000,001–$25,000,000). We display the
band and a midpoint estimate; the midpoint is arithmetic convenience, not data.

## Ownership ambiguity
Filings may be by spouse, dependent, or joint accounts ("owner" column shown
when available). A "member's trade" may not reflect the member's own decision.

## Performance attribution caveats
"Performance since trade" starts at the TRADE date (information the member had),
not the disclosure date (information you could have had). A follow-the-filing
strategy can only enter at disclosure — typically after most of any short-term
move. Member ranking uses 90-day forward alpha vs SPY and is **suppressed below
n=10 computable trades** ("INSUFFICIENT SAMPLE") because small-n leaderboards
are noise presented as skill.

## What conviction scoring does NOT include
Committee memberships and bill overlap have **no free machine-readable source**;
the conviction model scores only what it can see (cluster buying, repeat
purchases, size, recency) and says so on every score.

## Survivorship & coverage
Sector mapping covers a curated ticker list (coverage % displayed). Performance
is computed only for tickers with loaded price history. Unmapped/uncovered
records still appear — with dashes, not guesses.

## Integration policy
Congressional data is **context only**. It never enters the composite score,
the probability engine, or the allocation gate. If political-flow signals are
ever proposed as production inputs, they must pass the same pre-registered
train/test validation as everything else (see MODEL_REGISTRY.md rules).
