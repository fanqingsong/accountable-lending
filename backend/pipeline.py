"""Build one loan application as a scoped subgraph, then attach it to a graph."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
GRAPH_JSON = ROOT / "exports" / "lending_graph.json"
SEED_APPLICATION_ID = "sunrise-coffee"
SEED_APPLICANT_NAME = "Sunrise Coffee Roasters LLC"
ALLOWED_SUFFIXES = {".txt", ".pdf", ".docx", ".md"}


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w]+", "-", str(value).strip().lower()).strip("-")
    return slug or "application"


def reason_subject(applicant_name: str) -> str:
    subject = re.sub(r"[^A-Za-z0-9]", "", applicant_name)
    return subject or "Applicant"


def scope_id(application_id: str, raw: Any) -> str:
    value = str(raw or "")
    prefix = f"{application_id}::"
    if not value or value.startswith(prefix):
        return value
    return prefix + value


def scope_build_result(build_result: Dict[str, Any], application_id: str) -> Dict[str, Any]:
    """Prefix extracted ids so two applications cannot MERGE into one node."""
    entities = []
    for entity in build_result.get("entities") or []:
        metadata = dict(entity.get("metadata") or {})
        metadata["application_id"] = application_id
        entities.append(
            {
                **entity,
                "id": scope_id(application_id, entity.get("id") or entity.get("text")),
                "metadata": metadata,
            }
        )
    relationships = []
    for rel in build_result.get("relationships") or []:
        relationships.append(
            {
                **rel,
                "source": scope_id(application_id, rel.get("source") or rel.get("source_id")),
                "target": scope_id(application_id, rel.get("target") or rel.get("target_id")),
            }
        )
    return {"entities": entities, "relationships": relationships}


def ingest_files(paths: List[Path]) -> List[Dict[str, str]]:
    from semantica.ingest import FileIngestor

    ingestor = FileIngestor()
    documents: List[Dict[str, str]] = []
    for path in paths:
        file_object = ingestor.ingest_file(path)
        text = file_object.text if hasattr(file_object, "text") else str(file_object.content)
        documents.append({"name": path.name, "text": text})
    return documents


def extract(documents: List[str]) -> Dict[str, Any]:
    """Extract entities and relationships with local spaCy-backed extractors."""
    from semantica.kg import GraphBuilder

    builder = GraphBuilder(resolve_conflicts=False)
    return builder.build(
        documents,
        ner_method="ml",
        extract_relations=True,
        relation_method="pattern",
    )


def to_nodes_edges(build_result: Dict[str, Any]) -> Dict[str, Any]:
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


def reason(graph, subject: str) -> List[str]:
    """Forward-chain HighRiskFlag ∧ ThinCreditHistory ⇒ RequiresManualReview."""
    from semantica.reasoning import Reasoner

    reasoner = Reasoner()
    reasoner.add_rule(
        "IF HighRiskFlag(?x) AND ThinCreditHistory(?x) "
        "THEN RequiresManualReview(?x)"
    )
    reasoner.add_fact(f"HighRiskFlag({subject})")
    reasoner.add_fact(f"ThinCreditHistory({subject})")

    conclusions = []
    for result in reasoner.forward_chain():
        conclusions.append(result.conclusion)
    return conclusions


def record_decision_chain(
    graph,
    application_id: str,
    applicant: str,
    entity_ids: List[str] | None = None,
    high_risk: bool = True,
    thin_credit: bool = True,
) -> Dict[str, str]:
    """Record the three Decisions, link them with CAUSED, hang them on the Application."""
    if entity_ids is None:
        entity_ids = [
            node.get("id")
            for node in (graph.to_dict() or {}).get("nodes") or []
            if node.get("id") and node.get("type") not in {"Application", "Document", "Decision"}
        ][:6]

    if high_risk:
        risk_outcome = "high_risk"
        risk_reason = (
            "Revenue concentration or missing repayment history flags this "
            f"applicant ({applicant}) as high risk."
        )
    else:
        risk_outcome = "standard_risk"
        risk_reason = f"No high-risk flags were raised for {applicant}."

    if high_risk and thin_credit:
        policy_outcome = "manual_review_required"
        policy_reason = (
            "Policy 7.3 requires manual review when revenue concentration "
            "exceeds 35% or when no external repayment record exists."
        )
        final_outcome = "referred_to_manual_review"
        final_reason = (
            "Automated approval is not permitted under Policy 7.3; the "
            "application is routed to the manual review queue."
        )
    else:
        policy_outcome = "policy_cleared"
        policy_reason = (
            "Policy 7.3 does not require manual review for this profile."
        )
        final_outcome = "approved"
        final_reason = (
            f"Automated approval is permitted for {applicant} under Policy 7.3."
        )

    decisions: Dict[str, str] = {}
    decisions["risk_classification"] = graph.record_decision(
        category="risk_classification",
        scenario=f"Loan application for {applicant}",
        reasoning=risk_reason,
        outcome=risk_outcome,
        confidence=0.87,
        entities=entity_ids,
        decision_maker="underwriting_agent",
    )
    decisions["policy_check"] = graph.record_decision(
        category="policy_check",
        scenario="Internal lending policy for first-time borrowers",
        reasoning=policy_reason,
        outcome=policy_outcome,
        confidence=0.95,
        entities=entity_ids,
        decision_maker="policy_engine",
    )
    decisions["final_decision"] = graph.record_decision(
        category="final_decision",
        scenario=f"Loan outcome for {applicant}",
        reasoning=final_reason,
        outcome=final_outcome,
        confidence=0.93,
        entities=entity_ids,
        decision_maker="underwriting_agent",
    )
    graph.add_edge(
        decisions["risk_classification"], decisions["policy_check"], "CAUSED"
    )
    graph.add_edge(
        decisions["policy_check"], decisions["final_decision"], "CAUSED"
    )
    attach_decision_chain(graph, application_id, decisions)
    return decisions


def _add_node(graph, node: Dict[str, Any]) -> None:
    metadata = dict(node.get("metadata") or {})
    graph.add_node(
        node["id"],
        node.get("type") or "Entity",
        content=node.get("content") or node.get("id"),
        **metadata,
    )


def attach_case(
    graph,
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, str]],
    member_ids: List[str],
) -> str:
    app_node = f"{application_id}::application"
    graph.add_node(
        app_node,
        "Application",
        content=applicant_name,
        application_id=application_id,
    )
    for document in documents:
        doc_id = f"{application_id}::doc::{document['name']}"
        graph.add_node(
            doc_id,
            "Document",
            content=document["name"],
            application_id=application_id,
            body=document.get("text") or "",
        )
        graph.add_edge(app_node, doc_id, "HAS_DOCUMENT")
    for node_id in member_ids:
        if node_id and node_id != app_node:
            graph.add_edge(app_node, node_id, "CONTAINS")
    return app_node


def apply_payload(
    graph,
    payload: Dict[str, Any],
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, str]],
) -> List[str]:
    member_ids: List[str] = []
    for node in payload.get("nodes") or []:
        if not node.get("id"):
            continue
        metadata = dict(node.get("metadata") or {})
        metadata.setdefault("application_id", application_id)
        _add_node(graph, {**node, "metadata": metadata})
        member_ids.append(node["id"])
    for edge in payload.get("edges") or []:
        source = edge.get("source") or edge.get("source_id")
        target = edge.get("target") or edge.get("target_id")
        if source and target:
            graph.add_edge(source, target, edge.get("type") or "related_to", weight=edge.get("weight", 1.0))
    attach_case(graph, application_id, applicant_name, documents, member_ids)
    return member_ids


def apply_case(
    graph,
    paths: List[Path],
    application_id: str,
    applicant_name: str,
    high_risk: bool = True,
    thin_credit: bool = True,
) -> Dict[str, Any]:
    """Extract, scope, decide, and hang the case off an Application node."""
    documents = ingest_files(paths)
    build_result = extract([item["text"] for item in documents])
    payload = to_nodes_edges(scope_build_result(build_result, application_id))
    entity_ids = apply_payload(graph, payload, application_id, applicant_name, documents)

    if high_risk and thin_credit:
        reason(graph, subject=reason_subject(applicant_name))
    decisions = record_decision_chain(
        graph,
        application_id,
        applicant=applicant_name,
        entity_ids=entity_ids[:6],
        high_risk=high_risk,
        thin_credit=thin_credit,
    )
    return {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "entity_count": len(entity_ids),
        "decisions": decisions,
        "document_names": [item["name"] for item in documents],
    }


def attach_decision_chain(graph, application_id: str, decisions: Dict[str, str]) -> None:
    """Hang the three Decisions on the Application (HAS_DECISION). CAUSED is already on the chain."""
    app_node = f"{application_id}::application"
    for decision_id in decisions.values():
        if not decision_id:
            continue
        graph.add_edge(app_node, decision_id, "CONTAINS")
        graph.add_edge(app_node, decision_id, "HAS_DECISION")


def list_applications(graph) -> List[Dict[str, Any]]:
    applications = []
    for node in (graph.to_dict() or {}).get("nodes") or []:
        if node.get("type") != "Application":
            continue
        metadata: Dict[str, Any] = {}
        for key in ("properties", "metadata"):
            extra = node.get(key)
            if isinstance(extra, dict):
                metadata.update(extra)
        applications.append(
            {
                "id": node.get("id"),
                "name": node.get("content") or metadata.get("content") or node.get("id"),
                "application_id": metadata.get("application_id")
                or (str(node.get("id") or "").split("::", 1)[0] if "::" in str(node.get("id") or "") else None),
            }
        )
    return applications


def ensure_seed_application(
    graph,
    application_id: str = "sunrise-coffee",
    applicant_name: str = "Sunrise Coffee Roasters LLC",
) -> None:
    """Hang a seed Application node on a graph that was built before case isolation."""
    nodes = (graph.to_dict() or {}).get("nodes") or []
    if any(node.get("type") == "Application" for node in nodes):
        return
    member_ids = [node.get("id") for node in nodes if node.get("id")]
    attach_case(graph, application_id, applicant_name, [], member_ids)


def build_seed_graph():
    """Rebuild the bundled Sunrise case as a scoped application."""
    from semantica.context import ContextGraph

    graph = ContextGraph()
    apply_case(
        graph,
        paths=sorted(DATA_DIR.glob("*.txt")),
        application_id=SEED_APPLICATION_ID,
        applicant_name=SEED_APPLICANT_NAME,
        high_risk=True,
        thin_credit=True,
    )
    write_graph_snapshot(graph)
    return graph


def write_graph_snapshot(graph, path: Optional[Path] = None) -> Path:
    """Atomically write ContextGraph JSON. A failed write leaves the old file."""
    dest = Path(path) if path is not None else GRAPH_JSON
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    wrote = False
    if hasattr(graph, "save_to_file"):
        graph.save_to_file(str(tmp))
        wrote = tmp.is_file()
    if not wrote:
        payload = graph.to_dict() if hasattr(graph, "to_dict") else {}
        tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(dest)
    return dest
