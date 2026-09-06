# AGENT.md — Accountable Lending

Instructions for coding agents working in this repository. Cursor loads
[AGENTS.md](AGENTS.md), which points here. Product story and locked
decisions live in [SPEC.md](SPEC.md). Domain vocabulary is defined in
[CONTEXT.md](CONTEXT.md) — not folder paths. Architecture decisions live in
[docs/adr/](docs/adr/). Human setup lives in [README.md](README.md). Prefer
those files over inventing new architecture.

## What this is

A **deterministic, auditable small-business loan pipeline** on
[Semantica](https://github.com/semantica-agi/semantica). Seed case:
**Sunrise Coffee Roasters LLC** (`sunrise-coffee`). The point of the demo is
that the graph — not a prompt — can answer *why was this loan routed to
manual review?*

## Non-negotiable invariants

1. **No LLM in ingest, extract, reason, or `record_decision`.** Extraction is
   local spaCy. `record_decision` applies
   `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)`.
2. Chat (`backend/chat.py`) may call Ollama **only to write a short cited
   sentence from retrieve evidence**. If Ollama is down, fall back to an
   extractive paragraph. The LLM never writes the graph, never extracts,
   never records a decision.
3. Retrieve (`backend/retrieve/`) is GraphRAG **without generation**: keyword
   search always; Qdrant when `QDRANT_URL` is set.
4. Sample documents are **fictional**. Do not add real applicant data.
5. Causal links between decisions use the edge type **`CAUSED`** (uppercase).
   The traverser matches that exact type.
6. Entity ids for a case are prefixed `{application_id}::` so two applicants
   cannot MERGE into one Neo4j node.
7. RDF IRIs are minted only at export as
   `https://example.org/lending#<slug>`. Do not treat free-text ids as RDF
   subjects.
8. Turtle / SHACL is a **compliance export**, not the runtime store. Runtime
   is ContextGraph JSON + LPG in Neo4j.

## Architecture

Do not invent a new shape. Record or follow an ADR in `docs/adr/`.
Meta principles live in ADR-0000; coding shape (modular / KISS / DRY)
is ADR-0010; numbered ADRs specialize them.
Dependencies point inward: HTTP import and Prefect
tasks call `backend.application` leaves; `backend/application/` must not import
Prefect.

- [ADR-0000](docs/adr/0000-meta-design-principles.md) — Clean Architecture,
  DDD, and SOLID as lenses: inner Application/Decision modules, adapters
  at real seams, ubiquitous language. Not a folder template.
- [ADR-0001](docs/adr/0001-frontend-backend-separation.md) — lending UI and
  the JSON API are separate surfaces; do not grow server-rendered HTML.
- [ADR-0002](docs/adr/0002-no-generation-on-governed-path.md) — no LLM in
  ingest, extract, reason, or `record_decision`; chat only phrases retrieve
  evidence.
- [ADR-0003](docs/adr/0003-runtime-graph-vs-rdf-export.md) — runtime is
  ContextGraph + LPG; Turtle/SHACL is a compliance export.
- [ADR-0004](docs/adr/0004-application-scoped-entity-ids.md) — entity ids
  are `{application_id}::`; cases must not MERGE together.
- [ADR-0005](docs/adr/0005-caused-decision-chain.md) — Audit trail is the
  three-Decision `CAUSED` chain, not generated narrative.
- [ADR-0006](docs/adr/0006-three-http-adapters.md) — lending-api, lending-ui,
  Explorer.
- [ADR-0007](docs/adr/0007-react-antd-lending-ui.md) — React + Vite + Ant Design
  SPA for lending-ui.
- [ADR-0008](docs/adr/0008-ontology-single-source.md) — `ontology/lending.json`
  is the schema source of truth; OWL/SHACL are projections.
- [ADR-0009](docs/adr/0009-prefect-orchestrates-application.md) — Prefect
  composes the governed path; `backend/application/` stays Prefect-free; snapshot
  handoff between worker and lending-api. Pictures:
  [docs/runtime-flows.md](docs/runtime-flows.md).
- [ADR-0010](docs/adr/0010-modular-kiss-dry.md) — Modular packages, KISS,
  and DRY: name modules after CONTEXT terms; smallest change that honors
  the seam; one source of truth at a real seam. Not a `services/` tree.

## Layout

| Path | Role |
|---|---|
| `backend/application/` | Application attach, policy facts, snapshot load. No Prefect import. Public names stay on `backend.application`. Ingest / apply_payload / `record_decision` live under `prefect/lending_prefect/`. |
| `backend/retrieve/` | Chunks + entities + `CAUSED` chain. Public names stay on `backend.retrieve`. |
| `backend/paths.py` | Repo-relative paths (`GRAPH_JSON`, `DATA_DIR`, uploads, ontology files). |
| `backend/context_graph.py` | ContextGraph node/edge/property walk shared by Application, retrieve, and ontology. |
| `backend/snapshot.py` | Load or seed the ContextGraph snapshot via Prefect HTTP. Used by lending-api; Explorer only reads an existing file. |
| `prefect/lending_prefect/` | Prefect worker: `ingest.py` (files + spaCy extract + scoped payload), `application_flow`. Import as `lending_prefect` only from the worker. |
| `backend/prefect_api.py` | HTTP client for Prefect Server (`PREFECT_API_URL`). lending-api import / jobs / seed use this — not `lending_prefect`. |
| `backend/admin.py` | Explorer adapter: load ContextGraph snapshot, serve Knowledge Explorer on `:8000` |
| `backend/api.py` | lending-api boot: load snapshot (seed via flow), JSON on `:8001` |
| `backend/routes.py` | JSON `/api/lending/*` only — **do not** use `from __future__ import annotations` |
| `backend/import_service.py` | Upload TXT/PDF/DOCX/MD; refuse duplicate `application_id` |
| `backend/chat.py` | Retrieve first, then optional Ollama |
| `backend/ontology/` | Reads `ontology/lending.json` (ADR-0008); import validates required fields / relationships from that file. Public names stay on `backend.ontology`. |
| `backend/stores.py` | Neo4j MERGE + constraints (`entity_id` unique; property existence when edition allows) |
| `frontend/lending/` | React + Vite + Ant Design SPA (import / retrieve / chat / ontology). Calls the JSON API. Compose builds `dist`; nginx serves it. |
| `data/*.txt` | Seed Sunrise documents (`FileIngestor` reads these) |
| `data/samples/harbor-bakery/` | Second fictional pack |
| `ontology/` | `lending.json` (schema source of truth) + OWL/SHACL projections |
| `exports/` | Generated JSON/RDF/uploads — git-ignored |
| `tests/` | Fast unit tests default; real pipeline behind `integration` marker |
| `scripts/` | Host helpers: `run.sh`, `stop.sh`, spaCy wheel download. Not a home for domain code. |
| `docs/screenshots/` | Explorer / lending UI captures. Not product assets the pipeline reads. |
| `docs/runtime-flows.md` | Walkthrough of Prefect write path and retrieve / chat read path (Mermaid). Not an ADR. |
| `docs/agents/` | Issue tracker, triage labels, and domain-doc rules for engineering skills. Not runtime. |
| `.scratch/` | Local PRDs and implementation issues (tracker of record). Not runtime. Do not gitignore. |
| `docker-compose.yml` | `neo4j` + `qdrant` + `ollama` + `prefect-server` + `prefect-worker` + `lending-api` + `lending-ui` + `explorer` |

## Placement (do not invent a new tree)

[ADR-0000](docs/adr/0000-meta-design-principles.md) is a lens, not a
folder template. Name modules after [CONTEXT.md](CONTEXT.md) terms.

- **Inner:** Application attach, Decision recording, `CAUSED`, scoped
  ids — `backend/application/` and modules it already owns (`paths`,
  `context_graph`). No Prefect. Document ingest / extract:
  `prefect/lending_prefect/ingest.py`.
- **Adapters:** `prefect/lending_prefect/`
  (Prefect worker), `backend/prefect_api.py` (Prefect HTTP),
  `backend/snapshot.py` (seed/load snapshot), `backend/api.py` /
  `backend/routes.py`, `backend/admin.py` (Explorer), `backend/stores.py`,
  `backend/chat.py`, `frontend/lending/` (React SPA; see ADR-0007).
- **New capability:** JSON in `backend/routes.py` under `/api/lending/*`;
  UI in `frontend/lending/src/`. Do not compose HTML in Python
  ([ADR-0001](docs/adr/0001-frontend-backend-separation.md)).
- **Tests:** `tests/test_*.py` through the same seams (application,
  retrieve, `/api/lending/*`). Do not add helper packages for tests.
- **Do not add:** `app/`, `services/`, `use_cases/`, `repositories/`,
  `domain/`, a second frontend root, or HTML under `backend/`.
- A new top-level directory needs an ADR **or** an explicit update to
  the Layout table above. Do not leave a leftover tree beside `backend/`.

## Domain language

Use these names. Do not rename them to "service", "handler", or "agent step".

- **Application** — one loan case; seed id `sunrise-coffee`
- **Document** — an ingested applicant file (`HAS_DOCUMENT`)
- **Decision** — a recorded outcome with required `category` and `outcome`
- **Decision chain** — `risk_classification` → `policy_check` → `final_decision` linked by `CAUSED`
- **ContextGraph** — in-memory / JSON graph Explorer loads
- **LPG** — Neo4j system of record when `NEO4J_URI` is set
- **Audit trail** — `get_causal_chain(direction="upstream")` plus precedents

Required schema is `ontology/lending.json` only ([ADR-0008](docs/adr/0008-ontology-single-source.md)).
Today that file requires `Application.application_id`, `Decision.category`,
`Decision.outcome`, and `HAS_DECISION`. Optional there: `HAS_DOCUMENT`,
`CAUSED`. Do not keep a second required-field list in Python.

## Coding conventions

- Follow [ADR-0010](docs/adr/0010-modular-kiss-dry.md) on every change:
  modularize by CONTEXT terms, keep the change as small as the seam
  allows, and do not duplicate lending.json / paths / ContextGraph walks.
- Python 3.12, type hints, match existing style. Surgical diffs only.
- New lending capabilities: add or extend `/api/lending/*` JSON routes in
  `backend/routes.py`. New UI is a React page under `frontend/lending/src/`
  ([ADR-0001](docs/adr/0001-frontend-backend-separation.md),
  [ADR-0007](docs/adr/0007-react-antd-lending-ui.md)).
- Escape user text on the client. Do not compose markup in `routes.py`.
- Allowed upload suffixes: `.txt`, `.pdf`, `.docx`, `.md`.
- Docker: use `docker compose` (never `docker-compose`). Prefer Huawei
  mirror prefix `swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/` on
  public image names.
- Do not commit secrets, `exports/`, or the spaCy wheel under `docker/`
  unless the existing `scripts/run.sh` flow already expects it.
- Chat UI copy and extractive answers are Chinese; code and comments stay
  English unless the surrounding file is already Chinese.

## Commands

```bash
python -m pytest tests/ -q                 # default: skip integration
python -m pytest tests/ -q -m integration  # needs spaCy model
python -m lending_prefect.worker           # Prefect process runner (needs server; PYTHONPATH includes prefect/)
python -m backend.admin                    # Explorer at :8000 (needs snapshot)
python -m backend.api                      # JSON API at :8001
cd frontend/lending && npm run dev         # Vite at :5173/lending/
./scripts/run.sh                           # Neo4j + Qdrant + Ollama (pulls qwen2.5:1.5b) + three HTTP adapters
./scripts/stop.sh
LENDING_REBUILD=1 docker compose up lending-api  # rebuild graph from data/
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Do not add new dependencies unless the task requires them. If you do, update
  `requirements.txt` or `frontend/lending/package.json` and keep the Docker
  images buildable.

## Verify before claiming done

- Unit tests green (`python -m pytest tests/ -q`).
- If you touched ingest/extract/reason/decide/export: run
  `python -m pytest tests/ -q -m integration`.
- If you changed API or UI: verify the JSON contract (`/api/lending/*`)
  and exercise the client that consumes it. A single screenshot is not
  enough. Check every surface that shares the state you changed
  (`http://localhost:8080/lending*`, `/api/lending/*` on `:8001`,
  Explorer `/` on `:8000`).
- Success checks from SPEC: retrieve
  answers “为什么转人工” with risk-note chunks and the three-decision
  `CAUSED` chain; chat names that chain even when Ollama is missing;
  ontology page reports conformance.

## Do not

- Put an LLM, embeddings-only "reasoner", or opaque classifier into the
  decision path.
- Drop or rename `CAUSED`, scoped ids, or the three decision categories
  without updating retrieve, chat extractive fallback, ontology, and tests.
- Treat Turtle as the live store or skip SHACL when changing export.
- Expand scope into production KYC, real PII, or a general chatbot.
- Rewrite Semantica internals; wrap them. If a Semantica API is missing,
  fail visibly (`stage_failure` / user-facing error), do not hide it.
- Mix frontend rendering into Python (HTML templates, string-built markup,
  form-POST page handlers) for new lending features.
- Revive `app/` or grow a parallel package next to `backend/`.
- Add `services/`, `use_cases/`, `repositories/`, or `domain/` folders.
