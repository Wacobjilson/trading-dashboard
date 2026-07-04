# Knowledge Graph — institutional memory as structure

## Purpose
Answer provenance questions — "what experiments led us here?", "why was this
model retired?", "what evidence changed this belief?" — without re-reading
every doc.

## Inputs
Every `*.md` in the app dir (scanned for EXP-nn / GOV-nn citations), the
belief register (`/api/integrity`), the model registry (`/api/registry`).

## Outputs
`/api/director → graph`: nodes (doc / experiment / belief / model) + edges
(`cites`, `evidence`, `validated-by`). Rendered on the Research tab as an
experiment-centric index (EXP-11 ← which docs/beliefs/models cite it).

## How to query it
The graph is navigation; the *content* lives in the docs, which are RAG-
indexed — ask the AI in `ask` mode ("why was RS alpha retired?") and hybrid
retrieval pulls the cited sections.

## Validation
Every edge is verifiable: it exists iff the ID literally appears in the
source document/payload.

## Known limitations
Regex-scanned — prose references without IDs are missed; trades/journal
entries link only via their recorded regime/tags, not graph edges yet;
no temporal ordering on edges.

## Future roadmap
Edge timestamps from log dates; decision-journal and trade nodes; graph-aware
retrieval (boost chunks whose doc neighbors the queried entity).
