# AI Code Auditor

## Purpose
Periodic architectural critique of the codebase by the AI analyst — dead
code, duplicate logic, thread-safety risks, broad exception handling, missing
docs, testing gaps, config problems. **Suggestions only; the AI never
modifies code** (there is no code path for it to do so).

## Inputs
`_code_stats()` — a measured inventory, not source access: line/function/
route counts, thread and lock counts, broad-except-pass count, TODO/FIXME
count for quanta.py and index.html — plus RAG retrieval over the
architecture docs (AI_ARCHITECTURE.md, RESEARCH.md, this file).

## Outputs
`audit` mode in the AI drawer (button on the Research tab's Director card).
The report names which file/function a human should open and why, with
expected payoff per investigation.

## Why inventory instead of raw source
The full source (~7k lines) exceeds useful local-model context, and letting
an LLM free-read code invites confident hallucinated line references. The
inventory keeps claims checkable: every number it reasons from is measured.

## Validation
Inventory numbers are recomputed each call; anyone can verify them with grep.

## Known limitations
The auditor cannot see logic bugs — only structural signals; single-file
architecture is deliberate (zero-dependency deploy), so "split the file" is
pre-answered; local models may still over-generalize (treat as prompts for
human review, nothing more).

## Future roadmap
Per-endpoint latency capture (server-side timing log) to ground the "slow
endpoints" question with measurements; optional function-level source
excerpts on request for targeted review.
