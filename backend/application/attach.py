"""Attach Documents and the Decision chain to an Application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.application.ids import SEED_APPLICANT_NAME, SEED_APPLICATION_ID
from backend.application.policy import normalize_policy_facts
from backend.context_graph import node_properties, nodes_and_edges


def attach_case(
    graph,
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, str]],
    member_ids: List[str],
    policy_facts: Optional[Dict[str, Any]] = None,
) -> str:
    app_node = f"{application_id}::application"
    facts = normalize_policy_facts(policy_facts)
    graph.add_node(
        app_node,
        "Application",
        content=applicant_name,
        application_id=application_id,
        **facts,
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
    for node in nodes_and_edges(graph)[0]:
        if node.get("type") != "Application":
            continue
        metadata = node_properties(node)
        applications.append(
            {
                "id": node.get("id"),
                "name": node.get("content") or metadata.get("content") or node.get("id"),
                "application_id": metadata.get("application_id")
                or (str(node.get("id") or "").split("::", 1)[0] if "::" in str(node.get("id") or "") else None),
            }
        )
    return applications


def existing_application_ids(graph) -> set[str]:
    found: set[str] = set()
    for item in list_applications(graph):
        app_id = item.get("application_id") or ""
        if app_id:
            found.add(str(app_id))
        node_id = str(item.get("id") or "")
        if node_id.endswith("::application"):
            found.add(node_id[: -len("::application")])
    return found


def ensure_seed_application(
    graph,
    application_id: str = SEED_APPLICATION_ID,
    applicant_name: str = SEED_APPLICANT_NAME,
) -> None:
    """Hang a seed Application node on a graph that was built before case isolation."""
    nodes, _ = nodes_and_edges(graph)
    if any(node.get("type") == "Application" for node in nodes):
        return
    member_ids = [node.get("id") for node in nodes if node.get("id")]
    attach_case(graph, application_id, applicant_name, [], member_ids)
