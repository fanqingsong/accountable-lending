# Modular packages, KISS, and DRY

New code is organized by [CONTEXT.md](../../CONTEXT.md) concepts, kept
as small as the seam allows, and written once at a real seam. This
specializes [ADR-0000](0000-meta-design-principles.md): Clean Architecture
is still a lens, not a folder template. Agents generating or moving code
must follow this file.

**Status:** accepted (2026-09-06) — meta

## Context

Without an explicit coding-shape ADR, generation oscillates: paste a
`services/` / `use_cases/` tree, or dump every concern into one file and
copy path walkers and required-field lists. The 2026-09-06 `backend/`
reorganization chose a third path — packages named after Application,
retrieve, and the lending schema, with stable public imports — and that
choice is easy to undo by the next “cleanup.”

Vocabulary in this file (same as ADR-0000):

- **Module / interface / implementation / seam / adapter / depth /
  leverage / locality**
- **Application, Document, Decision, Decision chain, ContextGraph, Audit
  trail, lending schema**

## Decision

### Modularization (depth, not directory count)

- Name a module after a CONTEXT term or an existing Layout path. Do not
  name it Service, Handler, Manager, Helper, or Util.
- A package is justified when one **interface** hides several
  implementations (`backend.application`, `backend.retrieve`,
  `backend.ontology`). Re-export the public names from `__init__.py` so
  callers keep `from backend.application import …` / `from
  backend.retrieve import retrieve` / `from backend.ontology import …`.
- **Do not add** `app/`, `services/`, `use_cases/`, `repositories/`, or
  `domain/` ([AGENT.md](../../AGENT.md) Placement). One adapter is a
  hypothetical seam; two adapters make a real one (ADR-0000).
- Split a file when two reasons to change already live in it (schema vs
  validate vs OWL projection; attach vs policy facts). Do not split a
  50-line pass-through so every function has its own file.
- **Deletion test:** if deleting the new module only moves call-throughs,
  do not add it. If the same complexity would reappear in N callers, it
  earns its keep.
- Inner modules stay Prefect-free. Prefect HTTP and snapshot seed live
  in adapters (`backend/prefect_api.py`, `backend/snapshot.py`).
- New capability still lands as `/api/lending/*` in `backend/routes.py`
  plus UI under `frontend/lending/` ([ADR-0001](0001-frontend-backend-separation.md)).

### KISS (smallest change that honors the seam)

- Prefer extending an existing module over a new package.
- Do not introduce a seam, protocol, factory, or config object for a
  single adapter. Do not add “flexibility” the current callers do not
  use.
- Surgical diffs: touch only what the request requires. Do not rename
  `CAUSED`, scoped ids, or the three Decision categories to look modular.
- Comments and identifiers stay English unless the surrounding file is
  already Chinese. Domain words stay as in CONTEXT.md.
- If a simpler in-place edit exists, take it. Folder moves still need
  this ADR plus an AGENT.md Layout update.

### DRY (one source of truth, not premature sharing)

These are the required single sources — do not grow a second copy:

| Fact | Lives in |
|---|---|
| Required Application / Decision fields and relationships | `ontology/lending.json` ([ADR-0008](0008-ontology-single-source.md)) |
| Repo paths (`GRAPH_JSON`, `DATA_DIR`, uploads, ontology files) | `backend/paths.py` |
| ContextGraph nodes / edges / property bags | `backend/context_graph.py` |
| Policy fact names (`HighRiskFlag`, `ThinCreditHistory`, `RequiresManualReview`) | `backend/application/` |
| Retrieve evidence shape (chunks, entities, `CAUSED` chain) | `backend/retrieve/` |

DRY does **not** mean:

- extract a helper used once
- share types across a seam that must stay independent (Application must
  not import Prefect; retrieve callers must not need Qdrant collection
  names)
- merge chat generation into retrieve to avoid a second function

A three-line local walk that would couple an adapter to an inner module
the wrong way may stay duplicated. Prefer locality over a shared
utility that fails the deletion test.

## Considered options

1. **Rely on ADR-0000 alone.** Rejected: 0000 forbids a starter layout
   but does not say how to grow `backend/` packages or when DRY applies.
2. **KISS/DRY only in AGENT.md.** Rejected: agents treat AGENT.md as
   layout; this is a numbered trade-off that later ADRs must not ignore.
3. **This ADR, cited from AGENT.md and Cursor rules (chosen).**

## Consequences

- Code generation starts from ADR-0000, then this file, then 0001–0009.
  A proposal that adds a service layer, a second required-field dict, or
  a new package for one function is out of policy unless a later ADR
  supersedes this one.
- Tests stay on the same public interfaces (`backend.application`,
  `backend.retrieve`, `backend.ontology`, `/api/lending/*`).
- Layout table in AGENT.md remains the tree of record. This ADR does not
  invent directories.
