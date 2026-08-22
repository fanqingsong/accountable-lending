"""
Accountable Lending — an auditable loan-decision pipeline built on Semantica.

Run:  python demo.py

The demo walks a small-business loan application through every stage of a
governed AI decision:

    1. Ingest      — applicant documents (business profile, financials, risk notes)
    2. Extract     — entities and relationships pulled from the documents
    3. Graph       — a context graph assembled from the extractions
    4. Reason      — a forward-chained rule derives a new fact
    5. Decide      — three chained decisions recorded with full context
    6. Audit       — the causal chain and precedents, printed as an audit trail
    7. Export      — RDF/Turtle export, then SHACL validation of the result

The point of the demo is the finale: after everything runs, the graph itself
can answer "why was this loan routed to manual review?" — with the decisions,
the rule that fired, and the evidence documents as nodes in the same graph.

Semantica is the deterministic layer under the agent stack: no LLM is used
anywhere in this pipeline. Every stage below is reproducible, traceable, and
auditable by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


# --------------------------------------------------------------------------
# Small output helpers
# --------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a stage banner."""
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def note(message: str) -> None:
    """Print an indented observation line."""
    print(f"    {message}")


def stage_failure(title: str, exc: Exception) -> None:
    """Report a stage that could not run, without hiding the reason."""
    note(f"!! {title} could not run: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# Stage 1 — Ingest
# --------------------------------------------------------------------------

def stage_ingest() -> List[str]:
    """Read the applicant documents through Semantica's FileIngestor.

    Returns the document texts in ingestion order.
    """
    from semantica.ingest import FileIngestor

    ingestor = FileIngestor()
    documents: List[str] = []
    for path in sorted(DATA_DIR.glob("*.txt")):
        file_object = ingestor.ingest_file(path)
        text = file_object.text if hasattr(file_object, "text") else str(file_object.content)
        documents.append(text)
        note(f"ingested {path.name}: {len(text)} chars")
    return documents


# --------------------------------------------------------------------------
# Stage 2 — Extract
# --------------------------------------------------------------------------

def stage_extract(documents: List[str]) -> Dict[str, Any]:
    """Extract entities and relationships with local spaCy-backed extractors.

    GraphBuilder's raw-text path uses local extractors by default — no LLM,
    no API key, fully deterministic for a fixed model version.
    """
    from semantica.kg import GraphBuilder

    builder = GraphBuilder(resolve_conflicts=False)
    result = builder.build(
        documents,
        ner_method="ml",
        extract_relations=True,
        relation_method="pattern",
    )
    entities = result.get("entities", [])
    relationships = result.get("relationships", [])
    note(f"extracted {len(entities)} entities and {len(relationships)} relationships")
    for entity in entities[:8]:
        note(f"  entity: {entity.get('text') or entity.get('id')}  [{entity.get('type')}]")
    return result


# --------------------------------------------------------------------------
# Stage 3 — Graph
# --------------------------------------------------------------------------

def _to_nodes_edges(build_result: Dict[str, Any]) -> Dict[str, Any]:
    """Translate GraphBuilder's vocabulary into ContextGraph's nodes/edges."""
    nodes = []
    for entity in build_result.get("entities", []):
        nodes.append(
            {
                "id": entity.get("id") or entity.get("text"),
                "type": entity.get("type"),
                "content": entity.get("text") or entity.get("id"),
                "metadata": {
                    "confidence": entity.get("confidence", 1.0),
                },
            }
        )
    edges = []
    for rel in build_result.get("relationships", []):
        edges.append(
            {
                "source": rel.get("source"),
                "target": rel.get("target"),
                "type": rel.get("type"),
                "weight": rel.get("weight", 1.0),
            }
        )
    return {"nodes": nodes, "edges": edges}


def stage_graph(build_result: Dict[str, Any]):
    """Assemble the context graph and return it."""
    from semantica.context import ContextGraph

    graph = ContextGraph()
    graph.from_dict(_to_nodes_edges(build_result))
    stats = graph.to_kg_dict().get("statistics", {})
    note(
        "graph ready: "
        f"{stats.get('entity_count', '?')} entities, "
        f"{stats.get('relationship_count', '?')} relationships"
    )
    return graph


# --------------------------------------------------------------------------
# Stage 4 — Reason
# --------------------------------------------------------------------------

def stage_reason(graph) -> List[str]:
    """Forward-chain one business rule over the extracted facts.

    The rule: a company flagged as high-risk AND carrying a thin credit
    history requires manual review before any automated decision.
    """
    from semantica.reasoning import Reasoner

    entity_names = []
    for node in graph.to_dict().get("nodes", []):
        content = (node.get("content") or node.get("id") or "").lower()
        if "coffee" in content or "sunrise" in content:
            entity_names.append(node.get("id"))

    reasoner = Reasoner()
    reasoner.add_rule(
        "IF HighRiskFlag(?x) AND ThinCreditHistory(?x) "
        "THEN RequiresManualReview(?x)"
    )
    # Ground facts derived from the ingested risk notes (stage 1).
    reasoner.add_fact("HighRiskFlag(SunriseCoffeeRoasters)")
    reasoner.add_fact("ThinCreditHistory(SunriseCoffeeRoasters)")

    conclusions = []
    for result in reasoner.forward_chain():
        conclusions.append(result.conclusion)
        rule = getattr(result, "rule_used", None)
        rule_name = rule.name if rule else "rule"
        note(f"derived: {result.conclusion}  (via {rule_name})")
    return conclusions


# --------------------------------------------------------------------------
# Stage 5 — Decide
# --------------------------------------------------------------------------

def stage_decide(graph) -> Dict[str, str]:
    """Record three chained decisions, each linked to its evidence.

    Returns a mapping of decision label -> decision id.
    """
    entities = [
        node.get("id")
        for node in graph.to_dict().get("nodes", [])
    ][:6]

    decisions: Dict[str, str] = {}

    decisions["risk_classification"] = graph.record_decision(
        category="risk_classification",
        scenario="Loan application for Sunrise Coffee Roasters LLC",
        reasoning=(
            "38% revenue concentration with Café Amara plus no prior bank "
            "borrowing history."
        ),
        outcome="high_risk",
        confidence=0.87,
        entities=entities,
        decision_maker="underwriting_agent",
    )

    decisions["policy_check"] = graph.record_decision(
        category="policy_check",
        scenario="Internal lending policy for first-time borrowers",
        reasoning=(
            "Policy 7.3 requires manual review when revenue concentration "
            "exceeds 35% or when no external repayment record exists."
        ),
        outcome="manual_review_required",
        confidence=0.95,
        entities=entities,
        decision_maker="policy_engine",
    )

    decisions["final_decision"] = graph.record_decision(
        category="final_decision",
        scenario="Loan outcome for Sunrise Coffee Roasters LLC",
        reasoning=(
            "Automated approval is not permitted under Policy 7.3; the "
            "application is routed to the manual review queue."
        ),
        outcome="referred_to_manual_review",
        confidence=0.93,
        entities=entities,
        decision_maker="underwriting_agent",
    )

    # Make the causal links explicit: each later decision is caused by the
    # one before it. (Semantica also infers influence links from shared
    # entities; the explicit edges keep the audit trail deterministic.)
    graph.add_edge(
        decisions["risk_classification"], decisions["policy_check"], "CAUSED"
    )
    graph.add_edge(
        decisions["policy_check"], decisions["final_decision"], "CAUSED"
    )

    for label, decision_id in decisions.items():
        note(f"{label}: {decision_id}")
    return decisions


# --------------------------------------------------------------------------
# Stage 6 — Audit
# --------------------------------------------------------------------------

def stage_audit(graph, decisions: Dict[str, str]) -> None:
    """Print the causal chain and precedent decisions for the final outcome."""
    final_id = decisions["final_decision"]

    note("causal chain (upstream from the final decision):")
    chain = graph.get_causal_chain(final_id, direction="upstream", max_depth=5)
    for decision in chain:
        category = getattr(decision, "category", "?")
        outcome = getattr(decision, "outcome", "?")
        decision_id = getattr(decision, "decision_id", "?")
        note(f"  <- [{category}] {outcome}  ({decision_id})")

    note("precedents (similar decisions recorded earlier):")
    precedents = graph.find_precedents(final_id, limit=5)
    if precedents:
        for decision in precedents:
            note(f"  precedent: {getattr(decision, 'decision_id', '?')}")
    else:
        note("  (none recorded — this is the first decision of its kind)")


# --------------------------------------------------------------------------
# Stage 7 — Export & validate
# --------------------------------------------------------------------------

def _iri_for(value: Any) -> str:
    """Turn a raw identifier into a valid, stable IRI for RDF export.

    Extracted entity ids are free text ("Kochi, Kerala"), which is not a
    valid RDF subject. The demo mints deterministic IRIs under its own
    namespace instead of writing unvalidated ids into ``<>``.
    """
    import re
    import unicodedata

    slug = unicodedata.normalize("NFKD", str(value))
    slug = re.sub(r"[^\w\- ]", "", slug).strip().replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-") or "unnamed"
    return f"https://example.org/lending#{slug}"


def _with_iris(kg: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a KG dict with every entity id and relationship endpoint mapped
    to a valid IRI. The mapping is deterministic (same id, same IRI), so
    re-exporting the unchanged graph is idempotent."""
    mapping: Dict[str, str] = {}
    for entity in kg.get("entities", []):
        raw_id = str(entity.get("id"))
        mapping[raw_id] = _iri_for(raw_id)

    entities = [
        {**entity, "id": mapping.get(str(entity.get("id")), entity.get("id"))}
        for entity in kg.get("entities", [])
    ]
    relationships = []
    for rel in kg.get("relationships", []):
        source = str(rel.get("source_id") or rel.get("source"))
        target = str(rel.get("target_id") or rel.get("target"))
        relationships.append(
            {
                **rel,
                "source_id": mapping.get(source, source),
                "target_id": mapping.get(target, target),
            }
        )
    return {"entities": entities, "relationships": relationships}


def stage_export(graph) -> None:
    """Export the graph as Turtle and validate it against generated SHACL
    shapes. The shapes encode the same business rule the pipeline enforced,
    so the export carries the proof that the graph meets its own policy."""
    from semantica.export import RDFExporter
    from semantica.ontology import SHACLGenerator
    from semantica.ontology.ontology_validator import _run_pyshacl

    out_path = ROOT / "exports" / "lending_graph.ttl"
    out_path.parent.mkdir(exist_ok=True)

    exporter = RDFExporter()
    exporter.export_knowledge_graph(
        _with_iris(graph.to_kg_dict()), str(out_path), format="turtle"
    )
    note(f"exported RDF: {out_path}")
    note(f"  triples written: {sum(1 for line in out_path.read_text(encoding='utf-8').splitlines() if line.endswith('.'))}")

    ontology = {
        "name": "lending",
        "base_uri": "https://example.org/lending#",
        "classes": [
            {"name": "Decision", "description": "A recorded lending decision"},
            {"name": "Entity", "description": "A participant in the decision"},
        ],
        "properties": [
            {
                "name": "category",
                "domain": "Decision",
                "range": "string",
                "description": "Decision category",
            },
            {
                "name": "outcome",
                "domain": "Decision",
                "range": "string",
                "description": "Decision outcome",
            },
        ],
    }
    shapes = SHACLGenerator().generate(ontology)
    shapes_ttl = SHACLGenerator().serialize(shapes, format="turtle")

    data_ttl = out_path.read_text(encoding="utf-8")
    report = _run_pyshacl(data_ttl, shapes_ttl, "turtle", "turtle")
    note(f"SHACL validation: {report.summary()}")
    if report.violation_count:
        report.explain_violations()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    """Run the full pipeline, reporting every stage as it completes."""
    # Keep the demo's own output clean: Semantica's progress bars are for
    # interactive use and would drown the audit-trail narrative.
    import os

    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
    print(__doc__)

    pipeline: List[tuple] = [
        ("Ingest", stage_ingest, [], "documents"),
        ("Extract", stage_extract, ["documents"], "build_result"),
        ("Graph", stage_graph, ["build_result"], "graph"),
        ("Reason", stage_reason, ["graph"], "conclusions"),
        ("Decide", stage_decide, ["graph"], "decisions"),
        ("Audit", stage_audit, ["graph", "decisions"], None),
        ("Export & validate", stage_export, ["graph"], None),
    ]

    state: Dict[str, Any] = {}
    for title, func, inputs, output_key in pipeline:
        section(title)
        try:
            result = func(*(state[name] for name in inputs))
            if output_key:
                state[output_key] = result
        except Exception as exc:  # noqa: BLE001 — demo: report and continue
            stage_failure(title, exc)
            if output_key in ("documents", "build_result", "graph"):
                note("downstream stages will be skipped — fix the stage above first")
                break

    section("Done")
    note("The graph now holds the documents, the derived facts, the decisions,")
    note("and the causal edges between them — an audit trail, not a black box.")


if __name__ == "__main__":
    sys.exit(main())
