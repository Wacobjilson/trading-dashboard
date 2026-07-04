# Prompt Library

Every AI request is: `AI_SAFETY` preamble + mode charge + grounded DATA
sections + retrieved DOCS + the user request. Templates live in `AI_MODES` /
`AI_ROLES` / `AI_DEBATES` in quanta.py — this file documents them.

## The safety preamble (prepended to every prompt, no exceptions)
1. Never give buy/sell instructions, sizes, entries/exits or allocation changes.
2. Ground every claim in the DATA/DOCS sections; name the section used.
3. Missing data → say "not in the provided data"; never estimate from memory.
4. Platform findings override model priors (RS alpha REJECTED, RSI(2) only
   replicated edge, composite DESCRIPTIVE, government context-only).
5. Concise, structured, explicit about uncertainty. Analyst, not chatbot.

## Modes (grounding parts in parentheses)
| Mode | Charge | Grounded in |
|---|---|---|
| ask | answer using only data+docs | regime, scores, opportunities, portfolio, government, macro, integrity (+RAG) |
| morning | FACTS / INTERPRETATION / UNCERTAINTY / OPEN QUESTIONS | regime, scores, opportunities, government, macro, options, portfolio, alerts, priorities, registry (+RAG) |
| market | current picture strictly from data | regime, scores, macro, options, opportunities |
| sector | score components, factors, gov exposure, base rates | regime, scores, opportunities, factors, government, probabilities (+RAG) |
| company | gov/policy profile only; fundamentals NOT in platform — must say so | government, scores, regime (+RAG) |
| portfolio | exposures, R-multiples, regime fit vs allocation engine; risks not trades | portfolio, regime, scores, allocation, options, government, alerts |
| government | what happened / why / who / what history shows / what's untested | government, scores, regime, portfolio (+RAG) |
| critique | weak assumptions, duplicate/missing experiments, data-quality risks | registry, integrity, assumptions, scorecard, calibration, priorities, hypotheses (+RAG) |
| journal | recurring strengths/mistakes with per-trade citations; small-n honesty | journal, portfolio, regime |
| models | degradation, weakening beliefs, unproven calibration; monitor-only recs | registry, scorecard, integrity, calibration, assumptions (+RAG) |
| experiment | pre-registered design: hypothesis, spec, fixed gate, sample-size reality | hypotheses, priorities, registry, integrity (+RAG) |
| explain | explain an attached platform payload, nothing else | attached payload + regime, scores (+RAG) |

## Committee (8 sequential voices, identical data block)
Bull Analyst · Bear Analyst · Macro Strategist · Risk Manager · Options
Strategist · Government Policy Analyst · Research Director (~150 words each),
then CIO synthesis: CONSENSUS / DISAGREEMENTS / EVIDENCE / UNKNOWNS /
RESEARCH REQUIRED. Personas argue interpretation; the shared data block is
the only fact source ("do not let personalities invent facts" is enforced by
the preamble + identical grounding).

## Debates (2 openings + 2 rebuttals + neutral moderator)
bull-bear · trend-meanrev · macro-technicals · gov-market · growth-value.
The moderator's charge: which claims were grounded vs rhetoric, where
evidence is genuinely insufficient, what test would settle it.

## Grounding parts registry (`AI_PARTS`)
Cache-only reads (never blocks on heavy computation): scores (compact),
regime, government (brief+titles+pipeline), options (SPY key fields),
portfolio, journal (closed trades), alerts, macro, factors, opportunities,
allocation, calibration, scorecard, registry, integrity, assumptions,
priorities, hypotheses, probabilities. A part that isn't computed yet is
sent as `UNAVAILABLE — not computed yet`, so the model states the gap
instead of inventing numbers.
