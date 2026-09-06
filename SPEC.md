# SPEC — Accountable Lending demo

## Goal

A small, deterministic, runnable-in-one-command demo that proves the core
value of Semantica for regulated decision-making: an audit trail that a
person (or a regulator) can read after the fact.

## Story

A small-business loan application for Sunrise Coffee Roasters LLC is processed
by a governed pipeline. The final decision is *"referred to manual review"* —
and the demo's finale reconstructs exactly why, from the graph: the documents
ingested, the entities extracted, the rule that fired, the three chained
decisions, and their causal edges.

## Stages (fixed)

1. **Ingest** — three plain-text applicant documents via `FileIngestor`
2. **Extract** — local spaCy NER + pattern relations via `GraphBuilder.build`
3. **Graph** — `ContextGraph.from_dict` (vocab: nodes/edges)
4. **Reason** — `Reasoner` forward-chains
   `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)`
5. **Decide** — three `ContextGraph.record_decision()` calls, linked with
   explicit `CAUSED` edges (the uppercase type the causal traverser matches)
6. **Audit** — `get_causal_chain(direction="upstream")` +
   `find_precedents()`, printed as the trail
7. **Export** — `ContextGraph.save_to_file` JSON for Explorer; MERGE into
   Neo4j when `NEO4J_URI` is set; optional `RDFExporter` (Turtle) after
   minting stable IRIs, then `_run_pyshacl` against generated shapes

## Admin UI (phase 0)

`python -m backend.admin` / Compose service `explorer` loads the
ContextGraph snapshot and serves Semantica Knowledge Explorer on `:8000`.
`python -m backend.api` / `lending-api` owns rebuild, persist, and JSON
on `:8001`. Instance data is LPG in Neo4j. Turtle is a compliance export,
not the runtime store. See [ADR-0006](docs/adr/0006-three-http-adapters.md).

## Case import (phase 1)

`GET http://localhost:8080/lending` serves the import UI (React SPA). `POST /api/lending/import` uploads
applicant files and returns JSON. Each case is scoped with
`{application_id}::` entity ids and an `Application` node (`CONTAINS` /
`HAS_DOCUMENT` / `HAS_DECISION`). Sunrise remains the seed case
(`sunrise-coffee`). A second fictional pack is `data/samples/harbor-bakery/`.

## GraphRAG retrieve (phase 2)

`POST /api/lending/retrieve` returns document chunks, matching entities, and
the `CAUSED` decision chain. `GET http://localhost:8080/lending/retrieve` is the retrieve page for
that API. Keyword search always runs; Qdrant is used when `QDRANT_URL` is
set. No LLM generation.

## Ontology (phase 4)

`ontology/lending.json` is the schema source of truth
([ADR-0008](docs/adr/0008-ontology-single-source.md)). OWL/SHACL are
projections. `GET /api/lending/ontology` returns that JSON, generated
Turtle, and live-graph validation; `GET http://localhost:8080/lending/ontology`
renders it. Import refuses a case that fails the JSON required fields /
relationships (today: `Decision.category` / `outcome` and `HAS_DECISION`).
Neo4j gets the `entity_id` unique constraint; property-existence
constraints follow the same required fields when the edition supports
them (Community skips them).

## Chat (phase 3)

`POST /api/lending/chat` calls retrieve first, then optionally asks Ollama
(`OLLAMA_URL`) to write a short answer from that evidence. `GET http://localhost:8080/lending/chat`
is the chat page. If Ollama is down, the API falls back to an extractive
paragraph from the decision chain. The LLM never writes the graph, never
extracts, and never records a decision.

## Non-goals (v1)

- No LLM in ingest / extract / reason / `record_decision`
- No real production data — the sample documents are fictional

## Decisions locked in

- Design principles (Clean Architecture, DDD, SOLID as lenses):
  [ADR-0000](docs/adr/0000-meta-design-principles.md)
- `SEMANTICA_DISABLE_PROGRESS=1` set inside `main()`/notebook so progress
  bars do not drown the audit-trail narrative
- Entity ids are minted as `https://example.org/lending#<slug>` at export
  time only (free-text ids are not valid RDF subjects; deterministic
  minting keeps re-export idempotent)
- Sample documents are `.txt` (universally supported by `FileIngestor`)
- Tests: fast unit tests run by default; the real-pipeline smoke test is
  gated behind the `integration` pytest marker
- Frontend / backend separation: [ADR-0001](docs/adr/0001-frontend-backend-separation.md)
  — UI in `frontend/lending/`; JSON over `/api/lending/*`
- React + Vite + Ant Design lending-ui: [ADR-0007](docs/adr/0007-react-antd-lending-ui.md)
- Three HTTP adapters: [ADR-0006](docs/adr/0006-three-http-adapters.md)
- No generation on the governed path:
  [ADR-0002](docs/adr/0002-no-generation-on-governed-path.md)
- Runtime ContextGraph / LPG vs RDF export:
  [ADR-0003](docs/adr/0003-runtime-graph-vs-rdf-export.md)
- Application-scoped entity ids:
  [ADR-0004](docs/adr/0004-application-scoped-entity-ids.md)
- `CAUSED` Decision chain as the Audit trail:
  [ADR-0005](docs/adr/0005-caused-decision-chain.md)
- Ontology JSON as schema source of truth:
  [ADR-0008](docs/adr/0008-ontology-single-source.md)

## Verification

- `python -m demo` exits 0 with all seven stage banners, JSON export, and
  the SHACL conformance line
- `python -m pytest tests/ -q` green; `-m integration` green
- `demo/demo.ipynb` executes top-to-bottom with the same results
- Compose `explorer` serves Explorer at `:8000` after `lending-api` is healthy
- `GET http://localhost:8080/lending/retrieve` answers “为什么转人工” with risk-note chunks and the
  `risk_classification → policy_check → final_decision` CAUSED chain
- `GET http://localhost:8080/lending/chat` answers the same question in a paragraph that names
  the decision chain; Ollama is optional
- `GET http://localhost:8080/lending/ontology` reports that the live graph conforms to the
  Application / Decision shapes
