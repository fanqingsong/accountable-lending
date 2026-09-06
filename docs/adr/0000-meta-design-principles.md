# META: design principles that constrain later ADRs

This repository follows Clean Architecture, DDD, and SOLID as **lenses**,
not as a folder template. Feature ADRs (0001+) specialize these rules.
A later ADR may deviate only by saying so and why.

**Status:** accepted (2026-09-06) — meta

## Context

Accountable Lending is a small, auditable loan pipeline. The valuable
core is an Application, its Documents, and a deterministic Decision
chain — not a web framework, a vector store, or a chat model.

Without a meta rule, reviews oscillate between two failure modes:
paste in UseCase / Entity / Repository trees that fail the deletion
test, or grow FastAPI routes and the `demo/` CLI until the domain has no
home. Clean Architecture, DDD, and SOLID already name the trade-off
we want. This ADR says how they apply *here*.

Vocabulary in this file:

- **Module / interface / implementation / seam / adapter / depth /
  leverage / locality** — how we talk about structure. Do not substitute
  "service", "handler", "API", or "boundary" when those words are the
  subject.
- **Application, Document, Decision, Decision chain, ContextGraph, LPG,
  Audit trail** — the domain language. New modules are named after these
  concepts, not after frameworks.

## Decision

### Clean Architecture (dependency rule)

Dependencies point inward, toward the governed loan story.

- **Inside:** Application attach, scoped entity ids, Decision recording,
  `CAUSED` / `HAS_DECISION`, schema checks that do not need HTTP or RDF.
- **Outside (adapters):** FastAPI routes, Explorer service, Neo4j LPG,
  Qdrant, Ollama, RDF/SHACL export, the lending-ui SPA in `frontend/lending/`.
- A CLI (`python -m demo`) and an HTTP import path are two adapters on the same
  inner modules. The printable seven-stage narrative must not own
  Decision or Application behavior.
- Do not add a layer whose deletion merely moves call-throughs. One
  adapter is a hypothetical seam; two adapters make a real one
  ([ADR-0001](0001-frontend-backend-separation.md) is the HTTP/UI pair;
  retrieve vs chat generation is another).

### DDD (language and consistency, not ceremony)

- One bounded context for v1: the lending audit pipeline. Do not split
  import, retrieve, and chat into separate contexts.
- Ubiquitous language is mandatory in code and ADRs. Do not rename
  Application / Decision / Audit trail to "case service" or "agent step".
- An **Application** is the consistency unit for a case: scoped ids,
  Documents, and the Decision chain travel together
  ([ADR-0004](0004-application-scoped-entity-ids.md),
  [ADR-0005](0005-caused-decision-chain.md)).
- The Audit trail is graph traversal, not a reconstructed narrative.
- Do not introduce aggregates, repositories, domain events, or CQRS
  unless a later ADR records a second consistency unit that actually
  varies.

### SOLID (as depth, not as file count)

- **S** — a module has one reason to change at its seam. Routes change
  when the JSON contract changes; they do not grow markup
  ([ADR-0001](0001-frontend-backend-separation.md)). `record_decision`
  does not change when Ollama is down ([ADR-0002](0002-no-generation-on-governed-path.md)).
- **O** — new persistence or generation backends are new adapters.
  Do not extend by sprinkling `if OLLAMA` / `if NEO4J` through Decision
  recording.
- **L** — an adapter honors the full interface, including failure.
  Chat's extractive fallback is required, not optional polish.
- **I** — callers of retrieve need chunks, entities, and the `CAUSED`
  chain. They must not need IRI minting, spaCy, or Qdrant collection
  names. IRI minting stays at RDF export
  ([ADR-0003](0003-runtime-graph-vs-rdf-export.md)).
- **D** — inner modules depend on small interfaces (persist graph,
  complete a cited sentence), not on Neo4j or Ollama types.

### How later ADRs use this file

- Record a feature ADR when a choice is hard to reverse and surprising.
- If a proposal fights this meta ADR (new inner dependency on HTTP,
  LLM on the governed path, RDF as runtime, global entity ids), reject
  it or explicitly supersede the conflicting numbered ADR.
- Wrapping Semantica is required. Rewriting Semantica internals is out
  of scope; missing APIs fail visibly.

## Considered options

1. **Full Clean Architecture / DDD starter layout** (entities,
   use-cases, controllers, repositories as directories). Rejected:
   the demo would grow shallow modules and hide the Decision chain.
2. **Principles only in AGENT.md, no ADR.** Rejected: AGENT.md is for
   agents' day-to-day invariants; this choice needs a numbered,
   citable trade-off.
3. **Interpret the three schools in this repo's language (this ADR).**
   Chosen.

## Consequences

- Architecture reviews start here, then apply 0001–0005. They do not
  re-propose "add a service layer" or "put an LLM in reason" without
  a new ADR.
- Known debt that already violates the dependency rule (runtime
  `pipeline` importing the `demo/` CLI) is to be removed by deepening
  the inner Application / Decision modules, not by documenting it as
  intended.
- Tests follow the same seams as callers. Prefer tests through
  Application attach, retrieve evidence, and JSON `/api/lending/*`
  over tests of pass-through helpers.
- This ADR does not by itself restructure the tree. Folder moves still
  need a feature ADR or a targeted change (as with `backend/`).
