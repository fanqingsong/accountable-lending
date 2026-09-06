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

- **lending-api** owns ContextGraph lifecycle, LPG persist, vector index,
  and `/api/lending/*` JSON. Default port `8001`. It does not serve HTML
  and does not construct Explorer.
- **lending-ui** hosts the lending UI (default port `8080`). It calls a
  configured API base URL and links to a configured Explorer URL. The
  host is a built React SPA ([ADR-0007](0007-react-antd-lending-ui.md)).
- **explorer** is Semantica Knowledge Explorer (default port `8000`). It
  loads `GraphSession` from the ContextGraph JSON snapshot written by
  lending-api. Reload after import is enough; no cross-process mutation
  bridge.
- Import, retrieve, chat, and ontology stay one bounded context. The
  CLI (`python -m demo`) is a fourth adapter, not a fifth microservice.
- Do not add `services/`, `app/`, `use_cases/`, `repositories/`, or
  `domain/` trees. Compose services map onto `backend/` and
  `frontend/lending/`.

This specializes ADR-0001: Explorer is a third-party *service*, not a
mount inside the lending process.

## Consequences

- Compose / `scripts/run.sh` start all three HTTP adapters.
- `LENDING_REBUILD` rebuilds only inside lending-api.
- Qdrant and Ollama remain lending-api infrastructure.
- Agents add JSON on lending-api and UI under `frontend/lending/`.
