# Prefect orchestrates Application assembly

Prefect composes the governed path into one Application. Inner Decision
and attach code stay in `backend/application/` and must not import Prefect.
The ContextGraph snapshot is the handoff between the worker and lending-api.

**Status:** accepted (2026-09-06)

## Context

`apply_case` and the demo stage table both assembled ingest → extract →
attach → `record_decision`. A second composer would drift. HTTP import
mutated the in-process graph; a Prefect worker cannot share that object.

## Decision

- **`application_flow` is the only assembler** of ingest, extract, attach,
  decide, validate, and persist. Document ingest / extract / scoped
  payload live in `prefect/lending_prefect/ingest.py`. `backend/application/`
  keeps Application attach, policy facts, and snapshot helpers.
- **Prefect is an adapter.** Tasks call leaves. `record_decision`, scoped
  ids, and `CAUSED` do not take Prefect types ([ADR-0000](0000-meta-design-principles.md),
  [ADR-0002](0002-no-generation-on-governed-path.md)).
- **Compose runs Prefect Server plus a process runner** (`python -m
  lending_prefect.worker` / `flow.serve`). The Prefect UI on `:4200` is
  infrastructure, not a fourth lending HTTP adapter
  ([ADR-0006](0006-three-http-adapters.md)).
- **Snapshot handoff.** Tasks do not return a `ContextGraph`. The worker
  writes `exports/lending_graph.json` only after validate. lending-api
  reloads that file when a job completes. Deployment concurrency is 1.
- **lending-api talks to Prefect Server over HTTP only**
  (`backend/prefect_api.py`). It does not import `lending_prefect` or
  call `application_flow` in-process. The worker writes
  `exports/jobs/{flow_run_id}.json`; the job route merges that file
  after `GET /flow_runs/{id}` says Completed.
- Tests and no-server fallbacks may call `lending_prefect` in-process
  when `PREFECT_API_URL` is unset.

## Considered options

1. **Prefect types inside `record_decision`.** Rejected: inner dependency
   on an orchestrator, fights ADR-0000.
2. **Keep `apply_case` and wrap it as one task.** Rejected: two assemblers.
3. **In-process Prefect only, no server.** Rejected for Compose: the chosen
   runtime is Server + worker. In-process remains the no-server fallback.
4. **This ADR.** Chosen.

## Consequences

- `LENDING_REBUILD` and missing snapshots submit a seed flow run through
  the Prefect API, then load the snapshot.
- lending-ui polls `GET /api/lending/jobs/{flow_run_id}`.
- Adapter code lives in top-level `prefect/lending_prefect/` so it is
  not mixed into `backend/application/`. The folder is not importable as
  `prefect` (that name is the installed library); the package is
  `lending_prefect`. Do not add a `flows/` or `services/` tree.
- Sequence and task diagrams:
  [runtime-flows.md](../runtime-flows.md).
