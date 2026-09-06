"""Lending schema derived from ``ontology/lending.json``.

OWL/SHACL files are projections of that JSON. Import validates the live
ContextGraph against the same required fields and relationships.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = ROOT / "ontology"
ONTOLOGY_JSON = ONTOLOGY_DIR / "lending.json"
OWL_TTL = ONTOLOGY_DIR / "lending.ttl"
SHACL_TTL = ONTOLOGY_DIR / "lending.shacl.ttl"

# Semantica record_decision uses the lowercase LPG label.
GRAPH_TYPE_ALIASES = {"Decision": ("Decision", "decision")}

ENTITY_ID_CONSTRAINT = (
    "lending_entity_id",
    "CREATE CONSTRAINT lending_entity_id IF NOT EXISTS "
    "FOR (n:LendingNode) REQUIRE n.entity_id IS UNIQUE",
)


def load_ontology() -> Dict[str, Any]:
    return json.loads(ONTOLOGY_JSON.read_text(encoding="utf-8"))


LENDING_ONTOLOGY = load_ontology()


def _type_names(domain: str) -> Tuple[str, ...]:
    return GRAPH_TYPE_ALIASES.get(domain, (domain,))


def required_fields(ontology: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Map graph node types to required property names from the JSON schema."""
    source = ontology or LENDING_ONTOLOGY
    fields: Dict[str, List[str]] = {}
    for prop in source.get("properties") or []:
        if not prop.get("required"):
            continue
        name = str(prop.get("name") or "")
        domain = str(prop.get("domain") or "")
        if not name or not domain:
            continue
        for type_name in _type_names(domain):
            bucket = fields.setdefault(type_name, [])
            if name not in bucket:
                bucket.append(name)
    return fields


def required_relationships(ontology: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    source = ontology or LENDING_ONTOLOGY
    found: List[Dict[str, str]] = []
    for rel in source.get("relationships") or []:
        if not rel.get("required"):
            continue
        name = str(rel.get("name") or "")
        domain = str(rel.get("domain") or "")
        if not name or not domain:
            continue
        found.append(
            {
                "name": name,
                "domain": domain,
                "range": str(rel.get("range") or ""),
            }
        )
    return found


def _lpg_label(domain: str) -> str:
    aliases = _type_names(domain)
    return aliases[-1]


def _constraint_name(label: str, field: str) -> str:
    if field == "application_id":
        return "application_id"
    return f"{label}_{field}"


def neo4j_constraints(ontology: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """Uniqueness is adapter-side; property existence follows required JSON fields."""
    rows = [ENTITY_ID_CONSTRAINT]
    seen = {ENTITY_ID_CONSTRAINT[0]}
    for prop in (ontology or LENDING_ONTOLOGY).get("properties") or []:
        if not prop.get("required"):
            continue
        domain = str(prop.get("domain") or "")
        field = str(prop.get("name") or "")
        if not domain or not field:
            continue
        label = _lpg_label(domain)
        name = _constraint_name(label, field)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            (
                name,
                "CREATE CONSTRAINT "
                f"{name}_exists IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{field} IS NOT NULL",
            )
        )
    return rows


def render_owl(ontology: Optional[Dict[str, Any]] = None) -> str:
    source = ontology or LENDING_ONTOLOGY
    base = str(source.get("base_uri") or "https://example.org/lending#")
    comment = str(source.get("description") or "").replace('"', '\\"')
    lines = [
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"@prefix lend: <{base}> .",
        "",
        f"<{base}> a owl:Ontology ;",
        '    rdfs:label "Accountable Lending" ;',
        f'    rdfs:comment "{comment}" .',
        "",
    ]
    for cls in source.get("classes") or []:
        name = cls.get("name")
        if name:
            lines.append(f"lend:{name} a owl:Class ; rdfs:label \"{name}\" .")
    lines.append("")
    for prop in source.get("properties") or []:
        name = prop.get("name")
        domain = prop.get("domain")
        if not name or not domain:
            continue
        lines.extend(
            [
                f"lend:{name} a owl:DatatypeProperty ;",
                f"    rdfs:domain lend:{domain} ;",
                "    rdfs:range xsd:string ;",
                f'    rdfs:label "{name}" .',
                "",
            ]
        )
    for rel in source.get("relationships") or []:
        name = rel.get("name")
        domain = rel.get("domain")
        rng = rel.get("range")
        if not name or not domain or not rng:
            continue
        lines.extend(
            [
                f"lend:{name} a owl:ObjectProperty ;",
                f"    rdfs:domain lend:{domain} ;",
                f"    rdfs:range lend:{rng} .",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_shacl(ontology: Optional[Dict[str, Any]] = None) -> str:
    source = ontology or LENDING_ONTOLOGY
    base = str(source.get("base_uri") or "https://example.org/lending#")
    fields = required_fields(source)
    lines = [
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        f"@prefix lend: <{base}> .",
        "",
    ]
    seen = set()
    for cls in source.get("classes") or []:
        name = str(cls.get("name") or "")
        required = fields.get(name) or []
        if not name or not required or name in seen:
            continue
        seen.add(name)
        lines.append(f"lend:{name}Shape a sh:NodeShape ;")
        lines.append(f"    sh:targetClass lend:{name} ;")
        for index, field in enumerate(required):
            more = " ;" if index < len(required) - 1 else " ."
            lines.append("    sh:property [")
            lines.append(f"        sh:path lend:{field} ;")
            lines.append("        sh:minCount 1 ;")
            if field == "application_id":
                lines.append(
                    "        sh:datatype <http://www.w3.org/2001/XMLSchema#string> ;"
                )
            lines.append(f"    ]{more}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
    fields = required_fields()
    for node in scoped:
        ntype = str(node.get("type") or "")
        required = fields.get(ntype)
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

    for rel in required_relationships():
        domain_types = set(_type_names(rel["domain"]))
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


def apply_schema_constraints(store) -> Dict[str, Any]:
    """Apply uniqueness always; property existence is Neo4j Enterprise-only."""
    applied = []
    skipped = []
    for name, cypher in neo4j_constraints():
        try:
            store.execute_query(cypher)
            applied.append(name)
        except Exception as exc:  # noqa: BLE001 — Community cannot require NOT NULL
            skipped.append({"name": name, "reason": f"{type(exc).__name__}: {exc}"})
    return {"applied": applied, "skipped": skipped}


def schema_public() -> Dict[str, Any]:
    owl = render_owl()
    shacl = render_shacl()
    return {
        "ontology": LENDING_ONTOLOGY,
        "owl_path": str(OWL_TTL),
        "shacl_path": str(SHACL_TTL),
        "owl": owl,
        "shacl": shacl,
    }
