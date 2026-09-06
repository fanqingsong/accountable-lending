# React + Vite + Ant Design for lending-ui

lending-ui is a built React SPA in `frontend/lending/`. Ant Design is the
chrome and form layer. The Audit trail stays a custom Decision-chain view.
Compose builds the SPA, then nginx serves `dist` on `:8080`.

**Status:** accepted (2026-09-06)

## Context

ADR-0001 put markup in `frontend/lending/`. ADR-0006 made lending-ui a
separately deployable host that called `/api/lending/*`. Those pages were
vanilla HTML. The long-term UI is React, and Compose may run a frontend
build.

The demo still has four surfaces only: import, retrieve, chat, ontology.
Explorer on `:8000` stays a third-party service.

## Decision

- Stack: React, Vite, TypeScript, Ant Design (`antd`). No Umi, no Pro
  Components, no second frontend root.
- Source and `package.json` live in `frontend/lending/`. Vite `base` is
  `/lending/`. React Router `basename` is `/lending`. Public URLs stay
  `/lending`, `/lending/retrieve`, `/lending/chat`, `/lending/ontology`.
- `lending-ui` is a multi-stage image: Node builds `dist`, nginx serves it.
  Do not bind-mount source as the site root.
- API base and Explorer URL are Vite env (`VITE_LENDING_API_BASE`,
  `VITE_LENDING_EXPLORER_URL`), baked at image build. The client still
  speaks JSON only ([ADR-0001](0001-frontend-backend-separation.md)).
- Ant Design owns Layout, Menu, Form, Upload, Table, Alert, Empty, Spin.
  The Decision chain and retrieve evidence are custom components named
  after CONTEXT.md terms. Chat is the audit-desk layout (question left,
  evidence right). Do not ship the A/B/C prototype switcher.

This specializes ADR-0006: lending-ui remains a separate adapter; it is no
longer hand-written static HTML.

## Considered options

1. **Keep vanilla HTML** — smallest Docker image, weakest shared chrome.
   Rejected once React was the long-term stack.
2. **CDN React + antd UMD** — no build, poor DX. Rejected.
3. **Vite SPA + antd, built in Compose (this ADR).** Chosen.

## Consequences

- Agents add pages under `frontend/lending/src/`, not new `*.html` clients.
- `./scripts/run.sh` / `docker compose up --build lending-ui` compiles the
  SPA. Local Vite (`npm run dev`) uses `:5173`; CORS must allow it.
- Changing API copy still starts in `backend/routes.py`.
- Update AGENT.md Layout when this stack changes again.
