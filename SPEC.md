# SPEC — Accountable Lending demo

## Goal

A small, deterministic, runnable-in-one-command demo that proves the core
value of Semantica for regulated decision-making: an audit trail that a
person (or a regulator) can read after the fact.

## Story

A small-business loan application for Sunrise Coffee Roasters LLC is processed
by a governed pipeline. The final decision is *"referred to manual review"* —
and the demo's finale reconstructs exactly why, from the graph: the documents
ingested, the entities extracted, the rule that fired, the three chained
decisions, and their causal edges.

## Stages (fixed)

1. **Ingest** — three plain-text applicant documents via `FileIngestor`
2. **Extract** — local spaCy NER + pattern relations via `GraphBuilder.build`
3. **Graph** — `ContextGraph.from_dict` (vocab: nodes/edges)
4. **Reason** — `Reasoner` forward-chains
   `HighRiskFlag(X) AND ThinCreditHistory(X) => RequiresManualReview(X)`
5. **Decide** — three `ContextGraph.record_decision()` calls, linked with
   explicit `CAUSED` edges (the uppercase type the causal traverser matches)
6. **Audit** — `get_causal_chain(direction="upstream")` +
   `find_precedents()`, printed as the trail
7. **Export** — `RDFExporter` (Turtle) after minting stable IRIs for
   free-text entity ids, then `_run_pyshacl` against generated shapes

## Non-goals (v1)

- No LLM calls, no API keys, no network at demo time (after first model pull)
- No web UI, no persistence store — the in-memory graph is the artifact
- No real production data — the sample documents are fictional

## Decisions locked in

- `SEMANTICA_DISABLE_PROGRESS=1` set inside `main()`/notebook so progress
  bars do not drown the audit-trail narrative
- Entity ids are minted as `https://example.org/lending#<slug>` at export
  time only (free-text ids are not valid RDF subjects; deterministic
  minting keeps re-export idempotent)
- Sample documents are `.txt` (universally supported by `FileIngestor`)
- Tests: fast unit tests run by default; the real-pipeline smoke test is
  gated behind the `integration` pytest marker

## Verification

- `python demo.py` exits 0 with all seven stage banners and the SHACL
  conformance line
- `python -m pytest tests/ -q` green; `-m integration` green
- `demo.ipynb` executes top-to-bottom with the same results
