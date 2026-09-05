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

`python -m app.admin` / Compose service `admin` loads the JSON (or rebuilds
the pipeline) and serves Semantica Knowledge Explorer. Instance data is LPG
in Neo4j. Turtle is a compliance export, not the runtime store.

## Case import (phase 1)

`GET /lending` uploads applicant files. Each case is scoped with
`{application_id}::` entity ids and an `Application` node (`CONTAINS` /
`HAS_DOCUMENT` / `HAS_DECISION`). Sunrise remains the seed case
(`sunrise-coffee`). A second fictional pack is `data/samples/harbor-bakery/`.

## GraphRAG retrieve (phase 2)

`POST /api/lending/retrieve` and `GET /lending/retrieve` return document
chunks, matching entities, and the `CAUSED` decision chain. Keyword search
always runs; Qdrant is used when `QDRANT_URL` is set. No LLM generation.

## Ontology (phase 4)

Checked-in OWL/SHACL lives in `ontology/`. `GET /lending/ontology` shows
required fields and validates the live graph. Import refuses a case that
is missing `Decision.category` / `outcome` or `HAS_DECISION`. Neo4j gets
the `entity_id` unique constraint; property-existence constraints are
applied when the edition supports them (Community skips them).

## Chat (phase 3)

`POST /api/lending/chat` and `GET /lending/chat` call retrieve first, then
optionally ask Ollama (`OLLAMA_URL`) to write a short answer from that
evidence. If Ollama is down, the page falls back to an extractive paragraph
from the decision chain. The LLM never writes the graph, never extracts,
and never records a decision.

## Non-goals (v1)

- No LLM in ingest / extract / reason / `record_decision`
- No real production data — the sample documents are fictional

## Decisions locked in

- `SEMANTICA_DISABLE_PROGRESS=1` set inside `main()`/notebook so progress
  bars do not drown the audit-trail narrative
- Entity ids are minted as `https://example.org/lending#<slug>` at export
  time only (free-text ids are not valid RDF subjects; deterministic
  minting keeps re-export idempotent)
- Sample documents are `.txt` (universally supported by `FileIngestor`)
- Tests: fast unit tests run by default; the real-pipeline smoke test is
  gated behind the `integration` pytest marker

## Verification

- `python demo.py` exits 0 with all seven stage banners, JSON export, and
  the SHACL conformance line
- `python -m pytest tests/ -q` green; `-m integration` green
- `demo.ipynb` executes top-to-bottom with the same results
- Compose `admin` serves Explorer at `:8000` after Neo4j is healthy
- `GET /lending/retrieve` answers “为什么转人工” with risk-note chunks and the
  `risk_classification → policy_check → final_decision` CAUSED chain
- `GET /lending/chat` answers the same question in a paragraph that names
  the decision chain; Ollama is optional
- `GET /lending/ontology` reports that the live graph conforms to the
  Application / Decision shapes
