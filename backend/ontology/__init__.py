"""Lending schema derived from ``ontology/lending.json``.

OWL/SHACL files are projections of that JSON. Import validates the live
ContextGraph against the same required fields and relationships.
"""

from backend.ontology.constraints import apply_schema_constraints, neo4j_constraints
from backend.ontology.projections import render_owl, render_shacl, schema_public
from backend.ontology.schema import (
    LENDING_ONTOLOGY,
    load_ontology,
    required_fields,
    required_relationships,
)
from backend.ontology.validate import validate_graph
from backend.paths import OWL_TTL, SHACL_TTL

__all__ = [
    "LENDING_ONTOLOGY",
    "OWL_TTL",
    "SHACL_TTL",
    "apply_schema_constraints",
    "load_ontology",
    "neo4j_constraints",
    "render_owl",
    "render_shacl",
    "required_fields",
    "required_relationships",
    "schema_public",
    "validate_graph",
]
