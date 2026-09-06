# Accountable Lending

An auditable small-business loan-decision pipeline built on
[Semantica](https://github.com/semantica-agi/semantica) — graph-native
infrastructure for context and accountable AI systems.

The demo walks a loan application for **Sunrise Coffee Roasters LLC** through
a governed AI decision and ends with the question every regulator asks:
**"why was this loan routed to manual review?"** — answered by the graph
itself, not by a prompt.

> **No LLM anywhere in this pipeline.** Extraction is local spaCy, reasoning
> is forward-chained rules, and every decision is a node in a context graph
> with provenance. That determinism is the point.

---

## The pipeline

```mermaid
flowchart LR
    A[Documents] --> B[Extract<br/>spaCy NER + relations]
    B --> C[ContextGraph]
    C --> D[Reason<br/>forward-chained rule]
    D --> E[Record decisions<br/>3 chained, causal edges]
    E --> F[Audit trail<br/>causal chain + precedents]
    C --> G[JSON + Neo4j LPG]
    C --> H[RDF export<br/>optional]
    H --> I[SHACL]
    G --> J[Explorer]
```

| Stage | What happens | Semantica module |
|---|---|---|
| 1. Ingest | Three applicant documents (business profile, financials, risk notes) are read through `FileIngestor` | `ingest` |
| 2. Extract | 40+ entities and 150+ relationships pulled from the documents by local spaCy-backed extractors | `kg.GraphBuilder` |
| 3. Graph | A `ContextGraph` assembled from the extractions — entities, relationships, weights | `context` |
| 4. Reason | `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)` forward-chains and derives a new fact | `reasoning` |
| 5. Decide | Three decisions recorded with full context and explicit `CAUSED` edges: risk classification → policy check → final outcome | `context` |
| 6. Audit | The causal chain is traversed back from the final decision; precedents are searched | `context` |
| 7. Export | ContextGraph JSON for Explorer, LPG write to Neo4j when `NEO4J_URI` is set, optional Turtle + SHACL | `export`, `ontology`, `graph_store` |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

python -m demo                 # audit trail on stdout; writes exports/
python -m backend.api          # JSON API at :8001 (writes the snapshot)
python -m backend.admin        # Explorer at :8000 (loads the snapshot)
```

Expected runtime: under a minute (the first run downloads the spaCy model).
lending-api needs `NEO4J_URI` only if you want the graph persisted to Neo4j;
Explorer itself serves the snapshot ContextGraph.

## Docker

Requires [Docker](https://docs.docker.com/get-docker/) with Compose v2 (`docker compose`).

```bash
./scripts/run.sh    # Neo4j + Qdrant + Ollama + three HTTP adapters
./scripts/stop.sh   # stop containers and remove the compose stack
```

`scripts/run.sh` downloads the spaCy model wheel into `docker/` if it is not already
present, starts Ollama and pulls `${OLLAMA_MODEL:-qwen2.5:1.5b}`, then starts Neo4j,
Qdrant, `lending-api`, `lending-ui`, and `explorer`. First boot runs the lending
pipeline inside lending-api, writes
`exports/lending_graph.json` (and optional Turtle), MERGEs the graph into Neo4j,
indexes chunks into Qdrant when available, and lets Explorer load that snapshot.

| Surface | URL |
|---|---|
| Knowledge Explorer | http://localhost:8000 |
| lending-api | http://localhost:8001/api/lending/applications |
| Case import | http://localhost:8080/lending |
| GraphRAG retrieve (no LLM) | http://localhost:8080/lending/retrieve |
| GraphRAG chat (LLM writes the sentence) | http://localhost:8080/lending/chat |
| Ontology / SHACL | http://localhost:8080/lending/ontology |
| Neo4j Browser | http://localhost:7474 (user `neo4j`, password `lending-demo`) |

Chat at `http://localhost:8080/lending/chat` retrieves first, then asks Ollama (`OLLAMA_URL`)
to write a short cited answer. `./scripts/run.sh` pulls `${OLLAMA_MODEL:-qwen2.5:1.5b}`
before the stack comes up. If the model is missing, the page still answers from
the decision chain. To pull by hand:

```bash
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Upload TXT / PDF / DOCX on `http://localhost:8080/lending`. Each case becomes an `Application`
node; entity ids are prefixed (`harbor-bakery::…`) so a second applicant
cannot MERGE into Sunrise's nodes. A second fictional pack lives in
`data/samples/harbor-bakery/`.

Rebuild the graph from `data/` on the next start:

```bash
LENDING_REBUILD=1 docker compose up lending-api
```

CLI-only audit trail (no UI):

```bash
docker compose --profile cli up --build --abort-on-container-exit demo
```

The first image build takes several minutes (Semantica pulls PyTorch and the
Explorer bundle; `lending-ui` runs `npm ci` + Vite). Later runs reuse the
cached images.

Local Vite (API already on `:8001`):

```bash
cd frontend/lending && npm install && npm run dev
# http://localhost:5173/lending/
```

## What the output looks like

```
========================================================================
  Reason
========================================================================
    derived: RequiresManualReview(SunriseCoffeeRoasters)  (via Rule 1)

========================================================================
  Audit
========================================================================
    causal chain (upstream from the final decision):
      <- [risk_classification] high_risk  (c866337f-…)
      <- [policy_check] manual_review_required  (ce1cd65a-…)

========================================================================
  Export & validate
========================================================================
    exported JSON: exports/lending_graph.json
    persisted LPG to Neo4j: 40 nodes, 150 edges
    exported RDF: exports/lending_graph.ttl
      triples written: 157
    SHACL validation: Graph conforms to all SHACL constraints.
```

## Why this matters

An AI agent that approves or rejects a loan has to survive a regulator's
"why?" months later. A vector database stores embeddings; it cannot show the
chain `risk notes → rule → decision → policy check → outcome`. This demo is
that chain, persisted as a graph:

- the **documents** that were ingested,
- the **entities** extracted from them,
- the **rule** that fired and the fact it derived,
- the **decisions** and the causal edges between them,
- the **LPG** in Neo4j (system of record) and the JSON Explorer loads,
- the optional **RDF export** any triplestore can read, validated against shapes.

Re-run `python -m demo` on modified data and the pipeline produces a *different*
trail — same mechanics, new evidence. That is the difference between
"the model said so" and "here is the audit trail".

## Testing

```bash
# Fast unit tests (default)
python -m pytest tests/ -q

# Integration smoke test — runs the real ingest→extract→reason→decide
# stages against the bundled data (needs the spaCy model)
python -m pytest tests/ -q -m integration
```

## Repository layout

```
demo/              CLI adapter (`python -m demo`) + notebook
backend/           lending-api, Explorer adapter, persist, import, retrieve, chat
frontend/lending/  React + Vite + Ant Design lending UI (JSON client)
data/              seed applicant documents + samples/harbor-bakery
ontology/          OWL + SHACL for Application / Decision
docker/            spaCy model wheel (downloaded by scripts/run.sh)
Dockerfile         container image definition
docker-compose.yml neo4j + qdrant + ollama + lending-api + lending-ui + explorer
scripts/           run.sh, stop.sh, model download
docs/screenshots/  Explorer / lending UI captures
tests/             unit tests + integration smoke test
exports/           generated JSON / RDF (git-ignored)
```

## License

MIT — see [LICENSE](LICENSE). Built on [Semantica](https://github.com/semantica-agi/semantica) (MIT).
