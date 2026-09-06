# Ontology page schema readout

Status: done

The lending ontology page should show the full **lending schema** (classes, properties, relationships) and a clear live-graph conformance report, without implying that OWL/SHACL is the editor or that extract is schema-driven.

## Problem Statement

The ontology page is titled as if it explains the loan schema, but it only lists three properties and dumps SHACL. A reader concludes that “the ontology” is those fields, that SHACL is what import checks, or that changing the page would change extract. Classes, required `HAS_DECISION`, and optional `HAS_DOCUMENT` / `CAUSED` are already in the JSON API and never appear. After ADR-0008 made `lending.json` the single schema document, the page still hides most of that document.

## Solution

Keep the page a **read-only readout** of `GET /api/lending/ontology`. Show classes, properties, and relationships from the lending schema. Show which required fields and relationships the live ContextGraph check actually used. Put OWL/SHACL behind a secondary surface and link to Explorer for the Turtle snapshot. Use Chinese product copy. Do not add schema editing or a new API.

## User Stories

1. As a reviewer, I want to see every schema class with its description, so that I know Application, Decision, Document, and Entity are distinct kinds of nodes.
2. As a reviewer, I want to see every schema relationship (name, domain, range, required), so that I do not think the ontology is only three properties.
3. As a reviewer, I want `HAS_DECISION` marked required, so that I understand why import refuses an Application with no Decision attach.
4. As a reviewer, I want `HAS_DOCUMENT` and `CAUSED` visible as optional, so that I do not promote `CONTAINS` or treat attach as the Audit trail.
5. As a reviewer, I want properties listed as “properties” (not “required fields only”), so that the heading matches the required column.
6. As a reviewer, I want a short list of what the live-graph check enforced, so that I know success means JSON-derived field and relationship rules, not a pyshacl run on the printed Turtle.
7. As a reviewer, I want a conformance banner that still names how many nodes were checked, so that I can see the check ran on the live ContextGraph.
8. As a reviewer, I want each violation to show node id, type, field, and message, so that I can tell a missing `outcome` from a missing `HAS_DECISION`.
9. As a reviewer, I want OWL and SHACL available but collapsed or on a secondary tab, so that Turtle is not the first thing I read.
10. As a reviewer, I want a link from the projection note to Explorer’s Ontology Hub, so that I can open `lending.ttl` without hunting the header.
11. As a reviewer, I want one sentence that the schema constrains the case skeleton, not spaCy extract, so that I do not expect Entity types to match the class list.
12. As a reviewer, I want one sentence that this page cannot edit the schema and that a JSON change needs an API reload, so that I do not treat the page as a configuration form.
13. As a reviewer, I want class, property, and relationship descriptions in Chinese, so that the page matches import / retrieve / chat.
14. As a reviewer, I want `CAUSED` described as Decision-to-Decision causality, so that I do not confuse it with `HAS_DECISION`.
15. As a reviewer, I want Entity described as an extracted participant or fact, so that I do not treat Application, Document, or Decision as Entity.
16. As an importer, I want the same required shape I will hit on import, so that the ontology page and a failed import tell the same story.
17. As an API client, I want the existing ontology JSON contract unchanged, so that the page can be finished without a backend migration.
18. As a maintainer, I want frontend types to include classes, relationships, owl, and violation fields, so that the client cannot silently drop half the payload.
19. As a maintainer, I want a small readout mapper from the API payload to table rows and a required-item checklist, so that display rules are not buried in JSX.
20. As a maintainer, I want the page to keep working when optional description fields are missing, so that a thin schema file still renders.
21. As a maintainer, I want empty class or relationship arrays to show an empty table, not a crash, so that a future JSON edit cannot blank the route.
22. As a maintainer, I want load and validation errors to stay a Chinese alert, so that a down lending-api is obvious.
23. As a maintainer, I want Compose / Vite to serve the same route `/lending/ontology`, so that existing bookmarks and SPEC checks still apply.
24. As a demo operator, I want no new environment variables, so that `run.sh` URLs stay valid.
25. As a domain reader, I want CONTEXT terms (Application, Document, Decision, Decision chain, ContextGraph, LPG, Audit trail, lending schema) used in copy, so that the page does not invent “case service” language.
26. As a future author of runtime schema edits, I want this PRD to refuse an edit form, so that ADR-0008 is not quietly reversed.

## Implementation Decisions

- **Modules.** No new top-level package. Change the lending-ui ontology surface only: widen the ontology payload types; add a readout mapper (payload → class rows, property rows, relationship rows, required checklist, normalized violations); render those in the existing ontology page. Do not change import, retrieve, chat, pipeline, or `validate_graph`.
- **Deep module.** The readout mapper is the isolatable piece: one function, no React, no HTTP. The page stays a thin adapter. Do not add a `domain/` or `services/` tree.
- **API.** Keep `GET /api/lending/ontology` as-is (schema document, generated OWL/SHACL, live ContextGraph validation). No new route, no PATCH, no per-Application validation rollup.
- **ADR.** Follow ADR-0008 (JSON is the schema source; OWL/SHACL are projections; no runtime mutation). Follow ADR-0003 (do not present Turtle as the live store). Follow ADR-0005 (do not rename `CAUSED` or the three Decision categories). Follow ADR-0001 (JSON in, client render).
- **Copy.** Chinese on the page. Map known schema names to Chinese descriptions in the readout mapper; fall back to the JSON `description` when no mapping exists. Do not require a lending-schema JSON shape change for this PRD.
- **Layout.** Classes table, properties table (heading not “必填字段”), relationships table, then conformance (banner + required checklist + violations). OWL/SHACL in collapse or tabs. Explorer link next to the projection sentence, using the existing Explorer base URL.
- **Boundary copy.** Two short notes: schema does not drive extract; the page is read-only and JSON changes apply after API reload.

## Testing Decisions

Good tests assert observable payload and mapper output, not Ant Design internals.

- **Backend.** Existing ontology route test remains the contract prior art. Optionally assert the payload still includes `classes` and `relationships` on the ontology object, so the page’s data assumptions stay pinned. Do not add HTML snapshot tests.
- **Readout mapper.** Preferred unit tests if a frontend test runner is added later. This repo today has no UI test runner and keeps tests in `tests/test_*.py`. For this slice, do not add a new JS test stack; verify the mapper by exercising `/lending/ontology` in the browser (conforming graph, tables present, Turtle not the first paint, Explorer link works). If a later issue adds a frontend runner, the mapper is the module to test first.
- **Out of test scope.** pyshacl, Neo4j constraints, import refusal paths already covered elsewhere.

## Out of Scope

- Runtime editing or persisting the lending schema
- Driving extract, attach, or `record_decision` from the schema
- Grouping validation by Application in the API
- Changing OWL/SHACL generators or `lending.json` required flags
- Renaming `CAUSED` or Decision categories
- New HTTP adapters or a second frontend root
- Chinese strings inside `lending.json` (optional later; this PRD maps in the UI)

## Further Notes

Conversation that produced this PRD: the ontology page was mistaken for an import generator, then for a hot-reloadable config. ADR-0008 made the JSON the single document; this PRD only makes that document visible. Suggested first implementation: types + mapper + tables + collapse Turtle + two boundary sentences. Chinese descriptions and richer violation rows can ship in the same change if cheap.

## Comments

2026-09-06: Issues 01–04 implemented and verified on `/lending/ontology`. Marked done.
