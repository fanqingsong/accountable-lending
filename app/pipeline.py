"""Build one loan application as a scoped subgraph, then attach it to a graph."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

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
    import demo

    documents = ingest_files(paths)
    build_result = demo.stage_extract([item["text"] for item in documents])
    payload = demo._to_nodes_edges(scope_build_result(build_result, application_id))
    entity_ids = apply_payload(graph, payload, application_id, applicant_name, documents)

    if high_risk and thin_credit:
        demo.stage_reason(graph, subject=reason_subject(applicant_name))
    decisions = demo.stage_decide(
        graph,
        applicant=applicant_name,
        entity_ids=entity_ids[:6],
        high_risk=high_risk,
        thin_credit=thin_credit,
    )
    app_node = f"{application_id}::application"
    for decision_id in decisions.values():
        graph.add_edge(app_node, decision_id, "CONTAINS")
        graph.add_edge(app_node, decision_id, "HAS_DECISION")
    return {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "entity_count": len(entity_ids),
        "decisions": decisions,
        "document_names": [item["name"] for item in documents],
    }


def list_applications(graph) -> List[Dict[str, Any]]:
    applications = []
    for node in (graph.to_dict() or {}).get("nodes") or []:
        if node.get("type") != "Application":
            continue
        metadata = node.get("metadata") or {}
        applications.append(
            {
                "id": node.get("id"),
                "name": node.get("content") or node.get("id"),
                "application_id": metadata.get("application_id"),
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
    import demo
    from semantica.context import ContextGraph

    graph = ContextGraph()
    apply_case(
        graph,
        paths=sorted(demo.DATA_DIR.glob("*.txt")),
        application_id="sunrise-coffee",
        applicant_name="Sunrise Coffee Roasters LLC",
        high_risk=True,
        thin_credit=True,
    )
    demo.stage_export(graph)
    return graph
