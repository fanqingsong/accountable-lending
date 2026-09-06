"""Read a ContextGraph as nodes, edges, and node property bags."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def nodes_and_edges(graph) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = graph.to_dict() if hasattr(graph, "to_dict") else {}
    return list(data.get("nodes") or []), list(data.get("edges") or [])


def node_properties(node: Dict[str, Any]) -> Dict[str, Any]:
    bag: Dict[str, Any] = {}
    for key in ("properties", "metadata"):
        extra = node.get(key)
        if isinstance(extra, dict):
            bag.update(extra)
    return bag
