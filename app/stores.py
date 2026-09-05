"""Neo4j LPG persistence for the lending ContextGraph.

Instance data lives here. RDF/Turtle remains an optional compliance export.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple


def connect_store():
    """Open a Neo4j GraphStore when ``NEO4J_URI`` is set; otherwise return None."""
    uri = os.environ.get("NEO4J_URI", "").strip()
    if not uri:
        return None
    from semantica.graph_store import GraphStore

    store = GraphStore(
        backend="neo4j",
        uri=uri,
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "lending-demo"),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    store.connect()
    return store


def _safe_label(node_type: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(node_type or "Entity"))
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "Entity"
    if cleaned[0].isdigit():
        cleaned = f"T_{cleaned}"
    return cleaned


def _safe_rel(edge_type: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(edge_type or "RELATED_TO")).upper()
    return cleaned.strip("_") or "RELATED_TO"


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _node_props(node: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = str(node.get("id") or "")
    props: Dict[str, Any] = {
        "entity_id": entity_id,
        "text": str(node.get("content") or node.get("text") or entity_id),
        "node_type": str(node.get("type") or "Entity"),
    }
    for bag in (node.get("metadata"), node.get("properties")):
        if isinstance(bag, dict):
            for key, value in bag.items():
                props[str(key)] = _scalar(value)
    return props


def _graph_payload(graph) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if hasattr(graph, "to_dict"):
        data = graph.to_dict() or {}
        return list(data.get("nodes") or []), list(data.get("edges") or [])
    kg = graph.to_kg_dict()
    nodes = [
        {
            "id": entity.get("id"),
            "type": entity.get("type"),
            "content": entity.get("text") or entity.get("id"),
            "metadata": {"confidence": entity.get("confidence", 1.0)},
        }
        for entity in kg.get("entities") or []
    ]
    edges = [
        {
            "source": rel.get("source_id") or rel.get("source"),
            "target": rel.get("target_id") or rel.get("target"),
            "type": rel.get("type"),
            "weight": rel.get("weight", 1.0),
        }
        for rel in kg.get("relationships") or []
    ]
    return nodes, edges


def persist_graph(graph, store=None) -> Dict[str, Any]:
    """MERGE the in-memory graph into Neo4j. No-op when Neo4j is not configured."""
    owned = store is None
    store = store if store is not None else connect_store()
    if store is None:
        return {"nodes": 0, "edges": 0, "skipped": True}

    nodes, edges = _graph_payload(graph)
    try:
        from app.ontology import apply_schema_constraints

        apply_schema_constraints(store)
        for node in nodes:
            entity_id = str(node.get("id") or "")
            if not entity_id:
                continue
            label = _safe_label(node.get("type"))
            store.execute_query(
                f"MERGE (n:LendingNode {{entity_id: $id}}) "
                f"SET n:`{label}` "
                f"SET n += $props",
                parameters={"id": entity_id, "props": _node_props(node)},
            )
        written_edges = 0
        for edge in edges:
            source = str(edge.get("source") or edge.get("source_id") or "")
            target = str(edge.get("target") or edge.get("target_id") or "")
            if not source or not target:
                continue
            rel = _safe_rel(edge.get("type"))
            weight = edge.get("weight", 1.0)
            store.execute_query(
                f"MATCH (a:LendingNode {{entity_id: $src}}), "
                f"(b:LendingNode {{entity_id: $tgt}}) "
                f"MERGE (a)-[r:`{rel}`]->(b) "
                f"SET r.weight = $weight",
                parameters={"src": source, "tgt": target, "weight": _scalar(weight)},
            )
            written_edges += 1
        return {"nodes": len(nodes), "edges": written_edges, "skipped": False}
    finally:
        if owned and hasattr(store, "close"):
            store.close()
