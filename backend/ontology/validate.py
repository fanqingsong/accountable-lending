"""Validate a live ContextGraph against lending.json. No RDF round-trip."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.context_graph import node_properties, nodes_and_edges
from backend.ontology.schema import (
    LENDING_ONTOLOGY,
    required_fields,
    required_relationships,
    type_names,
)


def _application_id(node: Dict[str, Any]) -> str:
    props = node_properties(node)
    if props.get("application_id"):
        return str(props["application_id"])
    node_id = str(node.get("id") or "")
    if "::" in node_id:
        return node_id.split("::", 1)[0]
    return ""


def _belongs(node: Dict[str, Any], application_id: str) -> bool:
    return _application_id(node) == application_id


def _outgoing(edges: Sequence[Dict[str, Any]], node_id: str, rel_name: str) -> bool:
    expected = rel_name.upper()
    for edge in edges:
        source = str(edge.get("source") or edge.get("source_id") or "")
        if source != node_id:
            continue
        if str(edge.get("type") or "").upper() == expected:
            return True
    return False


def validate_graph(graph, application_id: Optional[str] = None) -> Dict[str, Any]:
    """Check required fields and relationships from lending.json. No RDF round-trip."""
    nodes, edges = nodes_and_edges(graph)
    related_ids = set()
    if application_id:
        app_ids = {
            str(node.get("id") or "")
            for node in nodes
            if str(node.get("type") or "") == "Application" and _belongs(node, application_id)
        }
        for edge in edges:
            source = str(edge.get("source") or edge.get("source_id") or "")
            target = str(edge.get("target") or edge.get("target_id") or "")
            if source in app_ids:
                related_ids.add(target)
    scoped = [
        node
        for node in nodes
        if not application_id
        or _belongs(node, application_id)
        or str(node.get("id") or "") in related_ids
    ]
    violations: List[Dict[str, str]] = []
    fields = required_fields()
    for node in scoped:
        ntype = str(node.get("type") or "")
        required = fields.get(ntype)
        if not required:
            continue
        props = node_properties(node)
        for field in required:
            if props.get(field):
                continue
            if field == "application_id" and _application_id(node):
                continue
            violations.append(
                {
                    "id": str(node.get("id") or ""),
                    "type": ntype,
                    "field": field,
                    "message": f"{ntype} missing {field}",
                }
            )

    for rel in required_relationships():
        domain_types = set(type_names(rel["domain"]))
        for node in scoped:
            if str(node.get("type") or "") not in domain_types:
                continue
            node_id = str(node.get("id") or "")
            if _outgoing(edges, node_id, rel["name"]):
                continue
            violations.append(
                {
                    "id": node_id,
                    "type": str(node.get("type") or rel["domain"]),
                    "field": rel["name"],
                    "message": f"{rel['domain']} has no {rel['name']}",
                }
            )

    return {
        "conforms": not violations,
        "violations": violations,
        "checked": len(scoped),
        "ontology": LENDING_ONTOLOGY["name"],
    }
