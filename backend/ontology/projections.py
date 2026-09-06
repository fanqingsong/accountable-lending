"""OWL / SHACL projections of lending.json. Not the runtime store."""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.ontology.schema import LENDING_ONTOLOGY, required_fields
from backend.paths import OWL_TTL, SHACL_TTL


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
            lines.append(f'lend:{name} a owl:Class ; rdfs:label "{name}" .')
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


def schema_public() -> Dict[str, Any]:
    return {
        "ontology": LENDING_ONTOLOGY,
        "owl_path": str(OWL_TTL),
        "shacl_path": str(SHACL_TTL),
        "owl": render_owl(),
        "shacl": render_shacl(),
    }
