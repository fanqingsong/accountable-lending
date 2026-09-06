# Runtime flows: write the graph, then ask it

Decisions live in [ADR-0002](adr/0002-no-generation-on-governed-path.md)
and [ADR-0009](adr/0009-prefect-orchestrates-application.md). Domain words
live in [CONTEXT.md](../CONTEXT.md). This page is the walkthrough.

Two paths share one **ContextGraph**. They never share an in-memory object
across processes.

```mermaid
flowchart LR
    subgraph write["Governed path — Prefect writes"]
        Docs[Documents] --> Flow[application_flow]
        Flow --> Snap["exports/lending_graph.json"]
        Flow --> LPG[Neo4j LPG]
        Flow --> Q[(Qdrant chunks)]
    end
    subgraph read["Ask path — lending-api reads"]
        Snap --> API[lending-api reload]
        LPG -.-> API
        Q -.-> Retr[retrieve]
        API --> Retr
        Retr --> Chat[chat phrases evidence]
    end
```

| Path | May use an LLM? | System of record |
|---|---|---|
| Prefect `application_flow` | No | ContextGraph snapshot + LPG |
| `retrieve` | No | Same graph; Qdrant is optional recall |
| `chat` | Yes, only to phrase retrieve evidence | Still the graph. Chat is not the Audit trail |

---

## 1. Who talks to whom

lending-api never imports `lending_prefect`. The worker never mutates the
API process. The handoff is the snapshot file (and, after Complete, a
job JSON).

```mermaid
sequenceDiagram
    actor User
    participant UI as lending-ui :8080
    participant API as lending-api :8001
    participant Pref as Prefect Server :4200
    participant W as prefect-worker
    participant Disk as exports/lending_graph.json

    User->>UI: import Application + files
    UI->>API: POST /api/lending/import
    API->>API: write uploads, refuse duplicate application_id
    API->>Pref: create_flow_run application-flow/lending-application
    API-->>UI: 202 flow_run_id + SCHEDULED
    loop poll
        UI->>API: GET /api/lending/jobs/{id}
        API->>Pref: GET /flow_runs/{id}
    end
    Pref->>W: scheduled run
    W->>W: application_flow on a work copy
    W->>Disk: persist after validate
    W->>W: exports/jobs/{id}.json
    UI->>API: GET job COMPLETED
    API->>Disk: reload_graph
    Note over API: retrieve / chat now see the new Application
```

Seed on first boot is the same flow: `backend/snapshot.py` calls
`submit_seed_run` (Sunrise documents under `data/`) when the snapshot is
missing or `LENDING_REBUILD` is set.

`PREFECT_API_URL` unset (unit tests): `lending_prefect.flows` runs
`application_flow` in-process and keeps a local job map. Compose does not
use that path.

---

## 2. Prefect: assemble one Application

`application_flow` is the only assembler. Tasks call leaves. `record_decision`,
scoped ids, and `CAUSED` take no Prefect types.

Work happens on a copy `{snapshot}.{application_id}.work`. Success replaces
`exports/lending_graph.json`. Failure deletes the work file. Deployment
concurrency is 1.

```mermaid
flowchart TD
    Start[application_flow] --> Copy["copy snapshot → work file"]
    Copy --> Facts[normalize policy_facts]
    Facts --> Ingest["ingest_task<br/>FileIngestor → name + text<br/>skip policy_facts.json"]
    Ingest --> Extract["extract_task<br/>spaCy GraphBuilder<br/>ids become application_id::local"]
    Extract --> Attach["attach_task<br/>nodes + edges + attach_case<br/>fail if application_id exists"]
    Attach --> Decide["decide_task<br/>HighRiskFlag ∧ ThinCreditHistory<br/>→ RequiresManualReview<br/>three Decisions + CAUSED"]
    Decide --> Valid["validate_task<br/>ontology/lending.json"]
    Valid -->|conforms| Persist["persist_task<br/>atomic snapshot<br/>optional Neo4j MERGE<br/>optional Qdrant index"]
    Valid -->|violations| Fail[raise — discard work]
    Persist --> Job["exports/jobs/{flow_run_id}.json"]
    Fail --> Drop[unlink work file]
```

### Decide branch (deterministic)

Facts are already on the Application (`policy_facts.json` or the import
form). They are not invented at retrieve time.

```mermaid
flowchart TD
    F[policy_facts_from_graph] --> And{HighRiskFlag AND ThinCreditHistory?}
    And -->|yes| Stamp1["stamp RequiresManualReview = true"]
    And -->|no| Stamp0["stamp RequiresManualReview = false"]
    Stamp1 --> C1["risk_classification = high_risk"]
    C1 --> C2["policy_check = manual_review_required"]
    C2 --> C3["final_decision = referred_to_manual_review"]
    Stamp0 --> A1["risk_classification = standard_risk"]
    A1 --> A2["policy_check = policy_cleared"]
    A2 --> A3["final_decision = approved"]
    C3 --> Edges["CAUSED + HAS_DECISION"]
    A3 --> Edges
```

Code: `prefect/lending_prefect/flows.py` (compose), `ingest.py`,
`attach.py`, `decide.py`, `snapshot.py`. Inner attach / facts:
`backend/application/`. HTTP submit / poll: `backend/prefect_api.py`.

---

## 3. Query: retrieve first, chat only phrases

`POST /api/lending/retrieve` and `POST /api/lending/chat` share
`retrieve()`. Chat adds a sentence. Neither writes the graph.

```mermaid
flowchart TD
    Q[query string] --> Expand["expand_query<br/>aliases: 转人工, 为什么, 高风险<br/>query language only — not Application ids"]
    Expand --> KW["keyword_hits<br/>Document / Decision / Application"]
    Expand --> Vec{"QDRANT_URL set?"}
    Vec -->|yes| VH["vector_hits source=vector"]
    Vec -->|no| Empty[no vector hits]
    KW --> Merge[merge_hits by id]
    VH --> Merge
    Empty --> Merge
    Merge --> Hint{query names an Application?}
    Hint -->|yes| Filter[keep that application's chunks]
    Hint -->|no| FromHits[collect application_id from hits]
    Filter --> Walk
    FromHits --> Walk["related_entities + related_decisions<br/>CAUSED chain"]
    Walk --> Payload["chunks + entities + decisions + caused"]
    Payload --> RetrAPI["/api/lending/retrieve returns this"]
    Payload --> Gen[generate_answer]
```

Chat generation:

```mermaid
flowchart TD
    P[retrieve payload] --> Ctx["format_context<br/>DECISION / CAUSED / CHUNK / ENTITY"]
    Ctx --> Ev{decisions or chunks?}
    Ev -->|no| None["图谱里没有找到相关证据。"]
    Ev -->|yes| Ext[extractive_answer: name the chain]
    Ext --> Ol{"OLLAMA_URL and complete ok?"}
    Ol -->|yes| Sent["short Chinese sentence<br/>source = ollama"]
    Ol -->|timeout / missing| Ext2["same extractive paragraph<br/>source = extractive"]
```

UI chat (`ChatPage`) POSTs **only the current sentence**. No server-side
history. The right-hand panel is the latest evidence, not the chat log.

```mermaid
sequenceDiagram
    actor User
    participant UI as ChatPage
    participant API as /api/lending/chat
    participant R as retrieve
    participant O as Ollama optional

    User->>UI: 为什么转人工
    UI->>API: POST {query}
    API->>R: retrieve(graph, query, store)
    R-->>API: chunks + entities + CAUSED
    alt Ollama up and evidence present
        API->>O: system: only use graph evidence
        O-->>API: sentence
    else missing or error
        API->>API: extractive_answer
    end
    API-->>UI: payload + answer + source
    UI->>UI: sentence left, Decision chain + evidence right
```

Code: `backend/retrieve/` (search + expansion + audit walk),
`backend/chat.py`, `backend/routes.py`.

---

## 4. What each store is for

```mermaid
flowchart LR
    Snap[ContextGraph JSON] -->|reload| Mem[API in-memory graph]
    Mem --> Retr[retrieve / chat / ontology]
    Neo[(Neo4j LPG)] -->|system of record when configured| Persist[persist_task]
    Persist --> Snap
    Qd[(Qdrant)] -->|optional semantic hits| Retr
    RDF[Turtle / SHACL] -.->|compliance export only| Disk[not a read path]
```

A vector hit can surface a risk-note chunk. It cannot be the answer to
“why manual review?”. That answer is the **Audit trail**: Documents,
Entities, the derived `RequiresManualReview` fact, and the **CAUSED**
Decision chain.
