# `ontology/lending.json` is the lending schema source of truth

Required Application / Decision fields and required attach relationships
are defined once in `ontology/lending.json`. Import validation, the
ontology API, and OWL/SHACL projections read that file. They do not keep
a second handwritten required-field list.

**Status:** accepted (2026-09-06)

## Context

The ontology page and `GET /api/lending/ontology` already returned
`lending.json`, but `validate_graph` enforced a parallel
`REQUIRED_FIELDS` dict and a hardcoded `HAS_DECISION` check. OWL and
SHACL files repeated the same shape. Changing the JSON alone updated the
page and left the import gate unchanged.

That is configuration drift, not a product rule. ADR-0003 still holds:
the live case is the ContextGraph / LPG; Turtle is a compliance export.
ADR-0005 still holds: the Audit trail is the three-Decision `CAUSED`
chain. This ADR does not make extract or `record_decision` ontology-
driven, and it does not allow runtime schema edits.

## Decision

- **`ontology/lending.json` is the only schema document** for required
  properties and required relationships. `backend/ontology.py` derives
  validation from it (including the `decision` LPG label alias for
  `Decision`).
- **OWL (`lending.ttl`) and SHACL (`lending.shacl.ttl`) are projections**
  of that JSON. The ontology API serves generated text so the page cannot
  drift. Checked-in Turtle stays as the Explorer / review snapshot and
  must match the generator.
- **`entity_id` uniqueness** is an LPG adapter constraint
  ([ADR-0004](0004-application-scoped-entity-ids.md)), not a lending
  property in the JSON. It stays in the Neo4j adapter list.
- **No runtime mutation.** Changing the schema is a file change plus
  process reload. A later ADR would be required to persist edits or to
  drive attach / decide from the schema.
- Pipeline code may still *write* the core shape in Python. After it
  writes, import must validate against the JSON, not against a second
  list.

## Considered options

1. **Keep dual lists** — cheapest, but the ontology page lies. Rejected.
2. **OWL as the source** — fights [ADR-0003](0003-runtime-graph-vs-rdf-export.md)
   (RDF is not the runtime model). Rejected.
3. **JSON source, derived validation and RDF projections (this ADR).**
   Chosen.

## Consequences

- Adding an optional property is a JSON edit (plus regenerated Turtle).
  Adding a *required* property changes import rejection without a second
  Python list — still not a runtime PATCH.
- Do not rename `CAUSED` or the three Decision categories in the JSON
  without the same-change updates already required by ADR-0005.
- Do not treat this as permission to interpret the JSON as an extractor
  or as a Decision-chain builder.
