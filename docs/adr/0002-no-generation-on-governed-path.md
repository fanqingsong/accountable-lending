# No generation on the governed path

The loan pipeline is auditable because ingest, extract, reason, and
`record_decision` are deterministic. An LLM may only phrase retrieve
evidence in chat. It never writes the ContextGraph.

**Status:** accepted (2026-09-06)

## Context

The product story is “why was this loan routed to manual review?” answered
from the graph, not from a prompt. A reasonable later change is to drop an
LLM into extraction, rule firing, or `record_decision` to “improve”
accuracy. That would make the Decision chain unreproducible and the Audit
trail unreadable as evidence.

Retrieve already returns chunks, entities, and the `CAUSED` chain. Chat
exists only to turn that evidence into a short cited sentence.

## Decision

- **Ingest, extract, reason, and `record_decision` have no LLM.** Extraction
  stays local spaCy. The policy rule
  `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)`
  is applied when recording Decisions.
- **Retrieve is GraphRAG without generation.** Keyword search always runs;
  Qdrant is used when `QDRANT_URL` is set. Retrieve does not call Ollama.
- **Chat calls retrieve first.** Ollama (`OLLAMA_URL`) may write a short
  cited sentence from that evidence. If Ollama is down or fails, fall back
  to an extractive paragraph from the Decision chain.
- The LLM never writes the graph, never extracts, and never records a
  Decision.

## Considered options

1. **LLM in extract or reason** — richer entities and softer rules, but the
   Audit trail becomes a model version and a prompt. Rejected.
2. **Embeddings-only “reasoner” or opaque classifier for the final
   Decision** — same opacity. Rejected.
3. **Retrieve-then-optional-generation (this ADR)** — the graph stays the
   system of record; generation is a presentation adapter on retrieve
   evidence. Chosen.

## Consequences

- Adding an LLM, embeddings-only reasoner, or opaque classifier to the
  Decision path requires superseding this ADR, not a quiet code change.
- Chat tests and UI must stay correct when Ollama is missing.
- Architecture reviews should not re-propose “just generate the answer”
  inside retrieve, or “let the model record the Decision.”
