# Separate the lending frontend from the JSON API

Lending UI and lending API are different surfaces. New work talks JSON over
`/api/lending/*`; the backend does not compose HTML. Server-rendered
`/lending*` pages are legacy and shrink when touched, they do not grow.

**Status:** accepted (2026-09-06)

## Context

`backend/routes.py` currently does both: it exposes `/api/lending/*` JSON and
also `GET`/`POST` `/lending*` pages that `read_text` a template and splice
fragments (`_results_html`, `_answer_html`, `_applications_html`).
`/api/lending/import` even returns HTML. That mix made the demo fast, but
it couples pipeline changes to markup, blocks a distinct frontend, and
contradicts the direction we want agents to follow.

Explorer at `/` is Semantica Knowledge Explorer, not a lending page. It
is a third-party *service* ([ADR-0006](0006-three-http-adapters.md)),
not a mount inside the lending process.

## Decision

- **Backend** (`backend/*.py`, except leftover static page files) owns ingest,
  extract, reason, decide, retrieve, chat generation, ontology validation,
  and persistence. It speaks JSON (multipart only for file upload). It does
  not inject `{{placeholders}}` or return `HTMLResponse` for new work.
- **Frontend** owns layout, copy, and rendering. It calls `/api/lending/*`
  and renders the payload. New UI lives in a frontend tree, not string-built
  inside `routes.py`.
- `/api/lending/*` is JSON only. Errors are `{"error": "..."}` plus an HTTP
  status, never an HTML error page.
- Existing `/lending*` template splices are **legacy**. Do not add
  placeholders, form-POST page handlers, or new `*_page.html` files. When a
  legacy page is touched, move that interaction to JSON + client render.
- Do not fork Explorer into the lending UI; integrate through APIs or links.

## Considered options

1. **Keep server-rendered HTML + optional JSON** — cheapest for the current
   demo, but every new field becomes another splice in `routes.py`. Rejected
   for anything after the current pages.
2. **JSON API + separate frontend (this ADR)** — one contract, UI can move
   without touching pipeline code. Chosen.
3. **SSR framework in the same Python process** (Jinja, HTMX-as-the-app) —
   still binds markup to the FastAPI process. Rejected; HTMX or similar may
   appear only as a *client* of the JSON API, not as a reason to grow
   server HTML.

## Consequences

- New lending capabilities add or extend `/api/lending/*` first. A page
  without an API is incomplete.
- Import, retrieve, chat, and ontology are JSON-complete. `/api/lending/*`
  returns JSON (multipart in, JSON out for import).
- Tests assert JSON contracts in `tests/test_routes.py`. Do not add HTML
  snapshot tests for spliced pages.
- Agents must not "finish" a feature by adding HTML under `backend/`. New UI
  goes in `frontend/lending/` and talks to the API.
- `GET /lending*` only serves those static files (`FileResponse`). It does
  not interpolate graph data.
