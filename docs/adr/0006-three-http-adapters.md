# Three HTTP adapters, one Application context

lending-api, lending-ui, and Explorer are separately deployable adapters.
They share one Application bounded context. Explorer is a third-party
service that loads a ContextGraph snapshot.

**Status:** accepted (2026-09-06)

## Context

ADR-0001 separated JSON from markup. The demo still started as one HTTP
process: Explorer at `/`, lending HTML via FileResponse, and
`/api/lending/*` on the same origin. That hid the pairing of lending-ui
to lending-api and forced route-order hacks around Explorer's SPA
fallback.

## Decision

- **lending-api** owns the in-process ContextGraph (load / reload from
  snapshot), vector-store connection, and `/api/lending/*` JSON. Default
  port `8001`. It does not serve HTML and does not construct Explorer.
  Import and seed rebuild submit `application_flow`
  ([ADR-0009](0009-prefect-orchestrates-application.md)); they do not
  assemble ingest → decide in this process.
- **lending-ui** hosts the lending UI (default port `8080`). It calls a
  configured API base URL and links to a configured Explorer URL. The
  host is a built React SPA ([ADR-0007](0007-react-antd-lending-ui.md)).
- **explorer** is Semantica Knowledge Explorer (default port `8000`). It
  loads `GraphSession` from the ContextGraph JSON snapshot written by
  lending-api. Reload after import is enough; no cross-process mutation
  bridge.
- Import, retrieve, chat, and ontology stay one bounded context.
  Prefect UI (`:4200`) is orchestrator infrastructure, not a lending
  surface.
- Do not add `services/`, `app/`, `use_cases/`, `repositories/`, or
  `domain/` trees. Compose services map onto `backend/` and
  `frontend/lending/`.

This specializes ADR-0001: Explorer is a third-party *service*, not a
mount inside the lending process.

## Consequences

- Compose / `scripts/run.sh` start the three HTTP adapters plus Prefect
  Server and the process runner.
- `LENDING_REBUILD` submits or runs `application_flow` (seed Sunrise),
  then lending-api loads the snapshot.
- Qdrant and Ollama remain lending-api infrastructure; LPG persist runs
  in the flow's persist task.
- Agents add JSON on lending-api and UI under `frontend/lending/`.
