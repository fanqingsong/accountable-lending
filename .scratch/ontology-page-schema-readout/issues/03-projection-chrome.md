# Demote Turtle and state ontology-page boundaries

Status: done

## Parent

`.scratch/ontology-page-schema-readout/PRD.md`

## What to build

OWL and SHACL stay available as projections but are not the first paint (collapse or a secondary tab). The projection sentence links to Explorer using the existing Explorer base URL so a reviewer can open the Turtle snapshot without hunting only in the header.

Two short Chinese notes: the lending schema constrains the Application / Document / Decision skeleton, not spaCy extract; this page is read-only and a JSON schema change applies after API reload. No edit form, no new env vars, same `/lending/ontology` route.

## Acceptance criteria

- [x] OWL and SHACL are not the primary view; both texts remain reachable.
- [x] Projection copy links to Explorer.
- [x] Page states schema does not drive extract.
- [x] Page states it cannot edit the schema and that JSON changes need an API reload.
- [x] No schema PATCH and no new environment variables.
- [x] Browser check: default view is tables/conformance; opening projections shows Turtle; Explorer link works.

## Blocked by

- `.scratch/ontology-page-schema-readout/issues/01-schema-tables.md`

## Comments

OWL/SHACL are collapsed. Explorer link is http://localhost:8000/. Expanding SHACL showed ApplicationShape / DecisionShape Turtle.
