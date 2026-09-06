# Runtime is ContextGraph and LPG; RDF is a compliance export

Live instance data is the ContextGraph (JSON for Explorer) and, when
configured, LPG in Neo4j. Turtle and SHACL are an export for conformance
checks. They are not the runtime store.

**Status:** accepted (2026-09-06)

## Context

The repo ships OWL/SHACL under `ontology/` and can emit Turtle. That makes
it look as if RDF is the system of record. Treating free-text node ids as
RDF subjects also looks convenient. Both would break Explorer, Neo4j MERGE,
and idempotent re-export.

## Decision

- **Runtime** is ContextGraph JSON plus LPG in Neo4j when `NEO4J_URI` is
  set. Import, retrieve, chat, and ontology validation read this graph.
- **Turtle / SHACL is a compliance export**, produced after the graph
  exists. Skipping SHACL when changing export is not allowed; skipping RDF
  on the import path is allowed.
- **RDF IRIs are minted only at export** as
  `https://example.org/lending#<slug>`. Free-text ids are not RDF subjects.
  Deterministic minting keeps re-export idempotent.

## Considered options

1. **RDF as the live store** — one model for ontology and instance data,
   but Explorer and the Semantica ContextGraph API would become adapters
   on a second database. Rejected for v1.
2. **Mint IRIs at ingest** — every node id is a URI from the start, but
   MERGE, scoping, and demo readability get worse. Rejected.
3. **ContextGraph / LPG runtime + RDF export (this ADR).** Chosen.

## Consequences

- Do not add a SPARQL or Turtle read path as a substitute for retrieve.
- Ontology page and import schema checks validate the live ContextGraph,
  not a Turtle file.
- Architecture reviews should not re-propose “move runtime to the triple
  store” without superseding this ADR.
