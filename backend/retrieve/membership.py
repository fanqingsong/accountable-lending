"""Map graph members to an Application. Case membership is not a baked-in alias list."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from backend.context_graph import node_properties, nodes_and_edges
from backend.retrieve.query import expand_query


def application_id_of(node: Dict[str, Any], mapping: Dict[str, str] | None = None) -> str:
    meta = node_properties(node)
    app_id = meta.get("application_id")
    if app_id:
        return str(app_id)
    node_id = str(node.get("id") or "")
    if mapping and node_id in mapping:
        return mapping[node_id]
    if "::" in node_id and not node_id.startswith("http"):
        prefix = node_id.split("::", 1)[0]
        if prefix and prefix not in {"decision", "entity"}:
            return prefix
    return ""


def application_map(graph) -> Dict[str, str]:
    """Map member node ids to an application_id via HAS_DECISION / CONTAINS."""
    nodes, edges = nodes_and_edges(graph)
    apps: Dict[str, str] = {}
    for node in nodes:
        if str(node.get("type") or "") != "Application":
            continue
        node_id = str(node.get("id") or "")
        apps[node_id] = application_id_of(node) or (
            node_id.split("::", 1)[0] if "::" in node_id else node_id
        )
    mapping = dict(apps)
    for edge in edges:
        if str(edge.get("type") or "").upper() not in {"HAS_DECISION", "HAS_DOCUMENT", "CONTAINS"}:
            continue
        source = str(edge.get("source") or edge.get("source_id") or "")
        target = str(edge.get("target") or edge.get("target_id") or "")
        if source in apps and target:
            mapping[target] = apps[source]
    return mapping


def hinted_applications(graph, query: str) -> List[str]:
    """Resolve Application hints from the graph, not a baked-in case list."""
    expanded = expand_query(query).lower()
    hints = []
    nodes, _ = nodes_and_edges(graph)
    for node in nodes:
        if str(node.get("type") or "") != "Application":
            continue
        app_id = application_id_of(node)
        if not app_id:
            continue
        tokens = [app_id.lower(), *app_id.lower().split("-")]
        content = str(node.get("content") or node_properties(node).get("content") or "")
        tokens.extend(re.split(r"\s+", content.lower()))
        if any(token in expanded for token in tokens if len(token) > 2):
            if app_id not in hints:
                hints.append(app_id)
    return hints
