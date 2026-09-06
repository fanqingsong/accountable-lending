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
   local spaCy. Reasoning is the forward-chained rule
   `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)`.
2. Chat (`backend/chat.py`) may call Ollama **only to write a short cited
   sentence from retrieve evidence**. If Ollama is down, fall back to an
   extractive paragraph. The LLM never writes the graph, never extracts,
   never records a decision.
3. Retrieve (`backend/retrieve.py`) is GraphRAG **without generation**: keyword
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
Meta principles live in ADR-0000; numbered ADRs specialize them.
Dependencies point inward: `python -m demo` and HTTP import call `backend.pipeline`; `backend/` must not import the CLI.

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

## Layout

| Path | Role |
|---|---|
| `demo/` | Seven-stage CLI adapter (`python -m demo`) and `demo.ipynb`. One printable function per stage; it does not own Decision or Application behavior. |
| `backend/pipeline.py` | Application module: extract, reason, `record_decision` + `CAUSED`, scoped attach. CLI and HTTP import both call this. |
| `backend/admin.py` | Explorer adapter: load ContextGraph snapshot, serve Knowledge Explorer on `:8000` |
| `backend/api.py` | lending-api boot: load/rebuild graph, persist, index, JSON on `:8001` |
| `backend/routes.py` | JSON `/api/lending/*` only — **do not** use `from __future__ import annotations` |
| `backend/import_service.py` | Upload TXT/PDF/DOCX/MD; refuse duplicate `application_id` |
| `backend/retrieve.py` | Chunks + entities + `CAUSED` chain |
| `backend/chat.py` | Retrieve first, then optional Ollama |
| `backend/ontology.py` | OWL/SHACL from `ontology/`; import requires `Decision.category` / `outcome` and `HAS_DECISION` |
| `backend/stores.py` | Neo4j MERGE + constraints (`entity_id` unique; property existence when edition allows) |
| `frontend/lending/` | React + Vite + Ant Design SPA (import / retrieve / chat / ontology). Calls the JSON API. Compose builds `dist`; nginx serves it. |
| `data/*.txt` | Seed Sunrise documents (`FileIngestor` reads these) |
| `data/samples/harbor-bakery/` | Second fictional pack |
| `ontology/` | `lending.json` + OWL/SHACL |
| `exports/` | Generated JSON/RDF/uploads — git-ignored |
| `tests/` | Fast unit tests default; real pipeline behind `integration` marker |
| `scripts/` | Host helpers: `run.sh`, `stop.sh`, spaCy wheel download. Not a home for domain code. |
| `docs/screenshots/` | Explorer / lending UI captures. Not product assets the pipeline reads. |
| `docs/agents/` | Issue tracker, triage labels, and domain-doc rules for engineering skills. Not runtime. |
| `.scratch/` | Local PRDs and implementation issues (tracker of record). Not runtime. Do not gitignore. |
| `docker-compose.yml` | `neo4j` + `qdrant` + `ollama` + `lending-api` + `lending-ui` + `explorer`; `demo` is profile `cli` |

## Placement (do not invent a new tree)

[ADR-0000](docs/adr/0000-meta-design-principles.md) is a lens, not a
folder template. Name modules after [CONTEXT.md](CONTEXT.md) terms.

- **Inner:** Application attach, Decision recording, `CAUSED`, scoped
  ids — `backend/pipeline.py` and modules it already owns.
- **Adapters:** `demo/` (`python -m demo`), `backend/api.py` /
  `backend/routes.py`, `backend/admin.py` (Explorer), `backend/stores.py`,
  `backend/chat.py`, `frontend/lending/` (React SPA; see ADR-0007).
- **New capability:** JSON in `backend/routes.py` under `/api/lending/*`;
  UI in `frontend/lending/src/`. Do not compose HTML in Python
  ([ADR-0001](docs/adr/0001-frontend-backend-separation.md)).
- **Tests:** `tests/test_*.py` through the same seams (pipeline,
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

Required schema (see `ontology/lending.json`): `Application.application_id`,
`Decision.category`, `Decision.outcome`, `HAS_DECISION`. Optional:
`HAS_DOCUMENT`, `CAUSED`.

## Coding conventions

- Python 3.12, type hints, match existing style. Surgical diffs only.
- Keep `demo/` stages printable and independently understandable. Set
  `SEMANTICA_DISABLE_PROGRESS=1` so progress bars do not drown the trail.
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
python -m demo                             # seven banners, JSON, SHACL line
python -m backend.admin                    # Explorer at :8000 (needs snapshot)
python -m backend.api                      # JSON API at :8001
cd frontend/lending && npm run dev         # Vite at :5173/lending/
./scripts/run.sh                           # Neo4j + Qdrant + Ollama (pulls qwen2.5:1.5b) + three HTTP adapters
./scripts/stop.sh
LENDING_REBUILD=1 docker compose up lending-api  # rebuild graph from data/
docker compose --profile cli up --build --abort-on-container-exit demo
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Do not add new dependencies unless the task requires them. If you do, update
  `requirements.txt` or `frontend/lending/package.json` and keep the Docker
  images buildable.

## Verify before claiming done

- Unit tests green (`python -m pytest tests/ -q`).
- If you touched ingest/extract/reason/decide/export: run
  `python -m pytest tests/ -q -m integration` and/or `python -m demo`.
- If you changed API or UI: verify the JSON contract (`/api/lending/*`)
  and exercise the client that consumes it. A single screenshot is not
  enough. Check every surface that shares the state you changed
  (`http://localhost:8080/lending*`, `/api/lending/*` on `:8001`,
  Explorer `/` on `:8000`).
- Success checks from SPEC: demo exits 0 with all stage banners; retrieve
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
