"""Lending schema: OWL/SHACL files plus graph-level validation and Neo4j constraints.

Explorer Ontology Hub can load ``ontology/lending.ttl``. Import uses the same
required fields so a case cannot be persisted without category/outcome.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = ROOT / "ontology"
ONTOLOGY_JSON = ONTOLOGY_DIR / "lending.json"
OWL_TTL = ONTOLOGY_DIR / "lending.ttl"
SHACL_TTL = ONTOLOGY_DIR / "lending.shacl.ttl"

REQUIRED_FIELDS = {
    "Application": ["application_id"],
    "Decision": ["category", "outcome"],
    "decision": ["category", "outcome"],
}

NEO4J_CONSTRAINTS = [
    (
        "lending_entity_id",
        "CREATE CONSTRAINT lending_entity_id IF NOT EXISTS "
        "FOR (n:LendingNode) REQUIRE n.entity_id IS UNIQUE",
    ),
    (
        "decision_category",
        "CREATE CONSTRAINT decision_category_exists IF NOT EXISTS "
        "FOR (n:decision) REQUIRE n.category IS NOT NULL",
    ),
    (
        "decision_outcome",
        "CREATE CONSTRAINT decision_outcome_exists IF NOT EXISTS "
        "FOR (n:decision) REQUIRE n.outcome IS NOT NULL",
    ),
    (
        "application_id",
        "CREATE CONSTRAINT application_id_exists IF NOT EXISTS "
        "FOR (n:Application) REQUIRE n.application_id IS NOT NULL",
    ),
]


def load_ontology() -> Dict[str, Any]:
    return json.loads(ONTOLOGY_JSON.read_text(encoding="utf-8"))


LENDING_ONTOLOGY = load_ontology()


def _props(node: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for key in ("properties", "metadata"):
        extra = node.get(key)
        if isinstance(extra, dict):
            merged.update(extra)
    return merged


def _nodes_edges(graph) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = graph.to_dict() if hasattr(graph, "to_dict") else {}
    return list(data.get("nodes") or []), list(data.get("edges") or [])


def _application_id(node: Dict[str, Any]) -> str:
    props = _props(node)
    if props.get("application_id"):
        return str(props["application_id"])
    node_id = str(node.get("id") or "")
    if "::" in node_id:
        return node_id.split("::", 1)[0]
    return ""


def _belongs(node: Dict[str, Any], application_id: str) -> bool:
    return _application_id(node) == application_id


def validate_graph(graph, application_id: Optional[str] = None) -> Dict[str, Any]:
    """Check required Application/Decision fields. No RDF round-trip."""
    nodes, edges = _nodes_edges(graph)
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
    for node in scoped:
        ntype = str(node.get("type") or "")
        required = REQUIRED_FIELDS.get(ntype)
        if not required:
            continue
        props = _props(node)
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

    apps = [node for node in scoped if str(node.get("type") or "") == "Application"]
    for app in apps:
        app_id = str(app.get("id") or "")
        has_decision = any(
            str(edge.get("source") or edge.get("source_id") or "") == app_id
            and str(edge.get("type") or "").upper() == "HAS_DECISION"
            for edge in edges
        )
        if not has_decision:
            violations.append(
                {
                    "id": app_id,
                    "type": "Application",
                    "field": "HAS_DECISION",
                    "message": "Application has no HAS_DECISION",
                }
            )

    return {
        "conforms": not violations,
        "violations": violations,
        "checked": len(scoped),
        "ontology": LENDING_ONTOLOGY["name"],
    }


def apply_schema_constraints(store) -> Dict[str, Any]:
    """Apply uniqueness always; property existence is Neo4j Enterprise-only."""
    applied = []
    skipped = []
    for name, cypher in NEO4J_CONSTRAINTS:
        try:
            store.execute_query(cypher)
            applied.append(name)
        except Exception as exc:  # noqa: BLE001 — Community cannot require NOT NULL
            skipped.append({"name": name, "reason": f"{type(exc).__name__}: {exc}"})
    return {"applied": applied, "skipped": skipped}


def schema_public() -> Dict[str, Any]:
    return {
        "ontology": LENDING_ONTOLOGY,
        "owl_path": str(OWL_TTL),
        "shacl_path": str(SHACL_TTL),
        "owl": OWL_TTL.read_text(encoding="utf-8") if OWL_TTL.is_file() else "",
        "shacl": SHACL_TTL.read_text(encoding="utf-8") if SHACL_TTL.is_file() else "",
    }
