"""lending.json as the required-field source of truth."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from backend.paths import ONTOLOGY_JSON

# Semantica record_decision uses the lowercase LPG label.
GRAPH_TYPE_ALIASES = {"Decision": ("Decision", "decision")}


def load_ontology() -> Dict[str, Any]:
    return json.loads(ONTOLOGY_JSON.read_text(encoding="utf-8"))


LENDING_ONTOLOGY = load_ontology()


def type_names(domain: str) -> Tuple[str, ...]:
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
        for type_name in type_names(domain):
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
