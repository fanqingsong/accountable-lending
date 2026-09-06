# AGENTS.md

Cursor / coding-agent entry point. Day-to-day invariants, Layout, and
Placement live in [AGENT.md](AGENT.md). Domain words live in
[CONTEXT.md](CONTEXT.md). Decisions live in [docs/adr/](docs/adr/).

Do not invent a new tree. Follow **Placement** in AGENT.md and
[ADR-0010](docs/adr/0010-modular-kiss-dry.md) (modular / KISS / DRY):

- Inner Application / Decision work: `backend/application/` (and modules it owns).
  Prefect lives in `prefect/lending_prefect/` — not in application.
- Host scripts: `scripts/`.
- New JSON: `backend/routes.py` → `/api/lending/*`.
- New UI: `frontend/lending/` (no HTML under `backend/`).
- Do not add `app/`, `services/`, `use_cases/`, `repositories/`, or `domain/`.
- A new top-level directory requires an ADR or an AGENT.md Layout update.

## Agent skills

### Issue tracker

Issues and PRDs live as markdown under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default role strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) recorded as a `Status:` line. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
