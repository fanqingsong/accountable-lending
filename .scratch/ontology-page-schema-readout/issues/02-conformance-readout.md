# Explain live-graph conformance on the ontology page

Status: done

## Parent

`.scratch/ontology-page-schema-readout/PRD.md`

## What to build

The same ontology page states what the live ContextGraph check actually enforced: a short checklist of required properties and required relationships derived from the lending schema (not a claim that the printed SHACL was executed). The existing banner still reports whether the graph conforms and how many nodes were checked.

Violations list id, type, field, and message so a missing Decision `outcome` is distinguishable from a missing `HAS_DECISION`. Import and this page tell the same required shape. No new validate API and no per-Application rollup.

## Acceptance criteria

- [x] Conforming graph: banner plus a checklist of required fields and required relationships from the schema document.
- [x] Copy does not say the page ran SHACL / pyshacl on the Turtle block.
- [x] Each violation shows id, type, field, and message when those keys exist.
- [x] Client types include violation `type` and `field`.
- [x] Browser check: conforming seed graph shows the checklist; do not invent a broken graph in production data.

## Blocked by

- `.scratch/ontology-page-schema-readout/issues/01-schema-tables.md`

## Comments

Shipped with the ontology readout mapper. Live graph reported conforms (82 nodes) plus the four required items. Violation row formatting is in the page; no broken production graph was created.
