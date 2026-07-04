# AI Limitations & Safety Boundaries

**Evidence drives decisions. AI improves understanding.** The analyst layer
exists to explain, summarize, critique, compare, question, teach, document
and brainstorm. It never decides.

## Hard boundaries (by construction, not by promise)
- `ai_run()` **only reads** cached view payloads and returns text. There is
  no code path from any AI output into: trade creation, model weights,
  allocation, scoring, experiment definitions, validation results, registry
  stages, belief confidences, or state files. Nothing parses AI text back
  into the platform.
- The frontend never calls Ollama directly; every request passes through the
  backend's safety preamble and grounding.
- Promotion/retirement of models, approval of hypotheses, and changes to
  weights remain exclusively with the platform's pre-registered validation
  process (MODEL_REGISTRY.md rules).

## Prompt-level rules (enforced in every request's system message)
No buy/sell instructions, sizes, entries/exits; cite the DATA/DOCS section
for every claim; "not in the provided data" instead of estimates; the
platform's validated findings override the model's training priors.

## Known failure modes to keep in mind
- **LLMs can still hallucinate** despite grounding — treat any uncited claim
  as suspect; the payloads and docs are the source of truth, not the prose.
- **Sycophancy:** local models may agree with leading questions. Ask the
  critique/debate modes to attack a view, not confirm it.
- **Stale grounding:** parts are cache-only; a tab never opened may be
  UNAVAILABLE in the prompt (stated, not filled in).
- **Company mode** has no fundamentals data by design — the platform doesn't
  carry any; the prompt instructs the model to say so rather than recite
  remembered (possibly outdated) facts.
- **Reasoning models** (qwen3) think out loud; the UI hides `<think>` blocks
  but latency includes them.
- **Small local models** are weaker at long-table arithmetic — never accept
  computed numbers from the AI; every real number is already in the payloads.

## Privacy
With `AI_PROVIDER=ollama` nothing leaves this machine. Switching to a cloud
provider (anthropic adapter) sends the grounded snapshot (market data, your
positions, journal) to that provider — a deliberate, configured choice.
