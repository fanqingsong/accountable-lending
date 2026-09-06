# Show the full lending schema on the ontology page

Status: done

## Parent

`.scratch/ontology-page-schema-readout/PRD.md`

## What to build

A reviewer opening the ontology page sees the complete lending schema from the existing ontology JSON: classes, properties, and relationships. Property table heading is “属性”, not “必填字段”. Required flags stay on properties and relationships so `HAS_DECISION` reads as required and `HAS_DOCUMENT` / `CAUSED` as optional.

Widen the client payload types so classes and relationships are first-class. Introduce a readout mapper (no React) that turns the API body into table rows. Empty or missing description fields still render. Do not add a route or change validation.

Pin the JSON contract: the ontology object still includes `classes` and `relationships`.

## Acceptance criteria

- [x] Ontology page lists every class from the payload (name + description).
- [x] Ontology page lists every relationship (name, domain, range, required).
- [x] Properties table heading is not “必填字段”; required column remains.
- [x] Client types include classes and relationships; the page does not crash on missing descriptions or empty arrays.
- [x] Route test asserts the ontology JSON still has `classes` and `relationships`.
- [x] Browser check: `/lending/ontology` shows three tables on a conforming live graph.

## Blocked by

None - can start immediately

## Comments

Implemented with 02–04 in the same lending-ui change. Verified on http://localhost:8080/lending/ontology after rebuilding lending-ui.
