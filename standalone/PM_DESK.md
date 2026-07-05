# Always-On PM Desk (Phase 21)

A standing portfolio-manager view that runs 24/7: reads sector money-flow,
maintains an overweight/underweight book, and pushes buy/sell **call-outs** —
in two honest conviction tiers.

## The two-tier honesty rule (enforced everywhere)
- **VALIDATED** — RSI(2) timing calls. The one edge that survived out-of-sample
  testing, costs, Deflated Sharpe, regime robustness and a permutation null
  (FALSIFICATION_GATE.md). Act on these.
- **DIRECTIONAL** — sector-rotation positioning. Built on the RRG quadrants and
  the top-3/1m rotation model (a *candidate* edge: PF 2.92 but only 30 test
  trades). Cross-sectional RS **alpha was REJECTED** (EXP-11). So rotation
  call-outs tell you *where money is flowing*, not that a sector will
  outperform. Size them as context, never as proof.

Every call-out, book row, and AI sentence carries its tier. The desk never
presents directional as validated.

## What runs 24/7 (deterministic, in the 30-second alert sweep)
- **Money-flow read** (`pm_desk_view`): each sector's RRG quadrant
  (Leading / Weakening / Lagging / Improving) + RS momentum → an
  overweight/underweight book with High/Medium/Low conviction (agreement of
  quadrant + trend + rotation-model membership).
- **Rotation call-outs** (`_check_pm_alerts`): quadrant transitions are the
  classic rotation signal — *Improving/Leading* = money rotating IN (buy-side
  call-out), *Weakening/Lagging* = rotating OUT (trim call-out). Pushed through
  the standard alert engine → bell + browser notifications.
- **Stance flips**: risk-on ↔ risk-off shifts (cyclical vs defensive
  leadership) fire a higher-order positioning call-out.
- RSI(2) BUY/EXIT and setup/stop/target alerts continue as before.

## The AI PM voice (tight cadence)
`pm_loop` runs the `pm-desk` AI mode every `PM_CYCLE_HOURS` (default **4h**,
set 0 to disable) whenever Ollama is reachable, writing a standing brief with
explicit positioning and today's highest-conviction action, and pushing a
one-line digest. The MIOS 10-agent deep cycle still runs daily
(`MIOS_CYCLE_HOURS`).

## Where to see it
- **Intel tab** — PM Desk card at the top: stance, money-flow, OW/UW, live
  validated call-outs, the full book, the call-out log, and the AI brief.
- **Bell / browser notifications** — call-outs as they fire.
- **AI drawer** → *Portfolio manager brief* for the full narrative on demand.

## Hard limits (unchanged)
Nothing auto-trades. The PM advises; you execute in ThinkOrSwim. The desk is
allowed to say "no validated action today" — an always-on desk that always
finds a trade is a defect. Cadence is configurable; the model is idle between
cycles (it is not pegged 24/7 — see the AI status panel).
