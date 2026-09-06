# The Audit trail is an explicit CAUSED Decision chain

A final Decision is explained by traversing the graph, not by asking a
model to remember the story. The three Decisions
`risk_classification` → `policy_check` → `final_decision` are linked with
the edge type `CAUSED` (uppercase). The causal traverser matches that
exact type.

**Status:** accepted (2026-09-06)

## Context

Semantica’s causal walk is type-sensitive. A lowercase `caused`, a generic
`RELATED`, or “the LLM will narrate the chain” all look like
simplifications and would make retrieve and the demo finale lie.

The demo value is that a person can reconstruct *why* from Documents,
extracted entities, the rule that fired, and the three chained Decisions.

## Decision

- Every Application that completes decide records **three Decisions** with
  required `category` and `outcome`, in that category order.
- Adjacent Decisions are linked with **`CAUSED`** (uppercase only).
- The Audit trail is `get_causal_chain(direction="upstream")` plus
  precedents. Retrieve must return that chain with the chunks. Chat’s
  extractive fallback must name it.
- Do not rename `CAUSED` or the three categories without updating
  retrieve, chat fallback, ontology, and tests in the same change.

## Considered options

1. **Implicit causality in Decision text** — fewer edges, but retrieve
   cannot reconstruct the chain. Rejected.
2. **A single Decision node** — simpler schema, but the story has three
   governed steps. Rejected.
3. **Explicit `CAUSED` chain (this ADR).** Chosen.

## Consequences

- Ontology import requires `Decision.category` / `outcome` and
  `HAS_DECISION`. Those edges attach Decisions to the Application; they
  do not replace `CAUSED` between Decisions.
- This ADR does not say whether reasoner conclusions must drive
  `record_decision` outcomes. That coupling is still an open deepening
  question; do not treat the current boolean flags as locked.
