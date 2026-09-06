"""Hang extracted payload onto an Application. Decision recording is in decide.py."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.application import attach_case


def _add_node(graph, node: Dict[str, Any]) -> None:
    metadata = dict(node.get("metadata") or {})
    graph.add_node(
        node["id"],
        node.get("type") or "Entity",
        content=node.get("content") or node.get("id"),
        **metadata,
    )


def apply_payload(
    graph,
    payload: Dict[str, Any],
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, str]],
    policy_facts: Optional[Dict[str, Any]] = None,
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
            graph.add_edge(
                source, target, edge.get("type") or "related_to", weight=edge.get("weight", 1.0)
            )
    attach_case(
        graph,
        application_id,
        applicant_name,
        documents,
        member_ids,
        policy_facts=policy_facts,
    )
    return member_ids
