"""Neo4j uniqueness and property-existence constraints from lending.json."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.ontology.schema import LENDING_ONTOLOGY, type_names

ENTITY_ID_CONSTRAINT = (
    "lending_entity_id",
    "CREATE CONSTRAINT lending_entity_id IF NOT EXISTS "
    "FOR (n:LendingNode) REQUIRE n.entity_id IS UNIQUE",
)


def _lpg_label(domain: str) -> str:
    aliases = type_names(domain)
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
