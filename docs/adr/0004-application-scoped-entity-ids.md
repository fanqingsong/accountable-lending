# Isolate each Application with scoped entity ids

Two loan cases must not MERGE into one Neo4j node. Entity ids for a case
are prefixed `{application_id}::`. Each case has an Application node with
`HAS_DOCUMENT` and `HAS_DECISION`.

**Status:** accepted (2026-09-06)

## Context

Extracted names repeat across fictional packs (companies, people, flags).
Neo4j MERGE on raw labels would collapse Sunrise and Harbor into one
entity. A global namespace also makes retrieve’s Application membership
ambiguous.

## Decision

- Entity ids inside a case are `{application_id}::<local id>`.
- Each case has an **Application** node. Documents attach with
  `HAS_DOCUMENT` (and `CONTAINS`). Decisions attach with `HAS_DECISION`
  (and `CONTAINS`).
- Import refuses a duplicate `application_id`.
- Seed case remains `sunrise-coffee`. Additional fictional packs (for
  example `harbor-bakery`) are new Application ids, not aliases inside
  retrieve.

## Considered options

1. **Global entity ids** — smaller graph, but MERGE across cases is
   silent data loss. Rejected.
2. **Separate Neo4j database per Application** — isolation is total, but
   retrieve and Explorer cannot show more than one case. Rejected for the
   demo.
3. **Prefixed ids on one graph (this ADR).** Chosen.

## Consequences

- Scoping belongs with Application attach, not as an afterthought in
  retrieve string matching.
- Retrieve may use the prefix and Application edges to assign membership.
  Hard-coded case-name aliases are not part of this decision and should
  not spread.
- The `entity_id` unique constraint in Neo4j assumes these prefixed ids.
