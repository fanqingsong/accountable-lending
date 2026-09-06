# Accountable Lending

A deterministic, auditable small-business loan pipeline. It exists so a
person can reconstruct *why was this loan routed to manual review?* from
the graph — not from a prompt.

## Language

### Case

**Application**:
One loan case; the consistency unit for scoped ids, Documents, and the Decision chain.
_Avoid_: case service, loan file, ticket

**application_id**:
The stable identifier of an Application. Import refuses a duplicate. Seed `sunrise-coffee`; second pack `harbor-bakery`.
_Avoid_: case name, alias inside retrieve

**scoped entity id**:
An id minted as `{application_id}::<local id>` so two Applications cannot MERGE into one node.
_Avoid_: global bare ids, a database per Application

### Evidence

**Document**:
An ingested applicant file attached to an Application.
_Avoid_: attachment, upload blob

**Entity**:
A participant or fact extracted from Documents — not an Application, Document, or Decision.
_Avoid_: Neo4j node, RDF subject (as a catch-all)

**Governed path**:
Ingest, extract, reason, and `record_decision` — no LLM.
_Avoid_: agent step, pipeline service

### Decision

**Decision**:
A recorded outcome with required `category` and `outcome`.
_Avoid_: verdict, recommendation, chat answer

**Decision chain**:
The three Decisions in category order: `risk_classification` → `policy_check` → `final_decision`.
_Avoid_: a single Decision node, implicit causality in Decision text

**CAUSED**:
The Decision-to-Decision causal edge type (uppercase only).
_Avoid_: caused, RELATED, narrative causality

**HAS_DECISION**:
The Application-to-Decision attach edge. It does not replace **CAUSED**.
_Avoid_: treating attach as the Audit trail

**HAS_DOCUMENT**:
The Application-to-Document attach edge.
_Avoid_: CONTAINS as the canonical name

**Audit trail**:
Upstream walk of **CAUSED** plus precedents that explain a final Decision.
_Avoid_: generated narrative, a chat paragraph as evidence

**RequiresManualReview**:
The fact derived by `HighRiskFlag(X) AND ThinCreditHistory(X)`. The seed Application's final outcome is referred to manual review. Whether reasoner conclusions must drive `record_decision` outcomes is still open ([ADR-0005](docs/adr/0005-caused-decision-chain.md)); do not treat today's boolean flags as locked semantics.
_Avoid_: locking the current flags as the rule–Decision contract

### Runtime vs export

**ContextGraph**:
The runtime graph (in memory and as JSON the Explorer loads).
_Avoid_: triple store as the live model

**LPG**:
Labeled-property-graph instance data in Neo4j when configured — the system of record for live cases.
_Avoid_: SPARQL as a substitute for retrieve

**compliance export**:
Turtle / SHACL produced after the graph exists. RDF IRIs are minted only at export as `https://example.org/lending#<slug>`.
_Avoid_: RDF as the runtime store, free-text ids as RDF subjects

**lending schema**:
Required Application / Decision fields and required relationships, defined only in `ontology/lending.json` ([ADR-0008](docs/adr/0008-ontology-single-source.md)). OWL/SHACL are projections. Import validation reads this file.
_Avoid_: a second required-field list in Python; OWL as the live editor

## Relationships

- An **Application** has exactly one **application_id**.
- An **Application** has zero or more **Documents** (`HAS_DOCUMENT`).
- An **Application** that completes decide has exactly three **Decisions** (`HAS_DECISION`), one per category in the **Decision chain**.
- Adjacent **Decisions** in that chain are linked by **CAUSED**.
- **HAS_DECISION** attaches a **Decision** to an **Application**; it does not explain why the **Decision** was reached.
- **Entities** belong to one **Application** via **scoped entity ids**; they are extracted from **Documents**.
- The **Audit trail** explains a **final_decision** by traversing **CAUSED**. It does not explain a chat paragraph.
- Many **Applications** may share one **ContextGraph** / **LPG**; their **scoped entity ids** must not MERGE.
- A **compliance export** is derived from the **ContextGraph**; it is not the store retrieve or decide read.

## Example dialogue

> **Dev:** "When someone asks why Sunrise went to manual review, should chat write that story?"
> **Domain expert:** "Chat may phrase retrieve evidence. The answer is the **Audit trail**: the **Documents**, extracted **Entities**, the rule that derived **RequiresManualReview**, and the **CAUSED** **Decision chain**. If the graph cannot show `risk_classification` → `policy_check` → `final_decision`, we do not have an explanation."
> **Dev:** "Can we treat the Turtle file as the live case, since SHACL already checks it?"
> **Domain expert:** "No. Runtime is the **ContextGraph** and **LPG**. Turtle is a **compliance export**. And do not mint IRIs at ingest — free-text ids are not RDF subjects."

## Flagged ambiguities

- **"case"** was used for the loan file — resolved: the concept is **Application**; the id is **application_id**, not a case-name alias in retrieve.
- **"entity"** was used for any graph node or RDF subject — resolved: **Entity** is only an extracted participant or fact, never an Application, Document, or Decision.
- **"reason" / "reasoning"** was used for the rule stage, the `reasoning` text on a **Decision**, and chat phrasing — resolved: these are distinct; only the reason stage is on the **Governed path**.
- **"audit"** was used for a generated recap — resolved: the **Audit trail** is graph traversal, not an LLM restatement.
- **"CONTAINS"** appears in code as a membership edge — resolved: it is implementation attach, not a required ontology relation; do not promote it over **HAS_DOCUMENT** / **HAS_DECISION**.
