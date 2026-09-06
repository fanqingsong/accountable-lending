"""Applicant document ingest and extract. No Decision recording, no Prefect types."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from backend.application import POLICY_FACTS_FILENAME


def scope_id(application_id: str, raw: Any) -> str:
    value = str(raw or "")
    prefix = f"{application_id}::"
    if not value or value.startswith(prefix):
        return value
    return prefix + value


def scope_build_result(build_result: Dict[str, Any], application_id: str) -> Dict[str, Any]:
    """Prefix extracted ids so two applications cannot MERGE into one node."""
    entities = []
    for entity in build_result.get("entities") or []:
        metadata = dict(entity.get("metadata") or {})
        metadata["application_id"] = application_id
        entities.append(
            {
                **entity,
                "id": scope_id(application_id, entity.get("id") or entity.get("text")),
                "metadata": metadata,
            }
        )
    relationships = []
    for rel in build_result.get("relationships") or []:
        relationships.append(
            {
                **rel,
                "source": scope_id(application_id, rel.get("source") or rel.get("source_id")),
                "target": scope_id(application_id, rel.get("target") or rel.get("target_id")),
            }
        )
    return {"entities": entities, "relationships": relationships}


def ingest_files(paths: List[Path]) -> List[Dict[str, str]]:
    from semantica.ingest import FileIngestor

    ingestor = FileIngestor()
    documents: List[Dict[str, str]] = []
    for path in paths:
        if Path(path).name == POLICY_FACTS_FILENAME:
            continue
        file_object = ingestor.ingest_file(path)
        text = file_object.text if hasattr(file_object, "text") else str(file_object.content)
        documents.append({"name": Path(path).name, "text": text})
    return documents


def extract(documents: List[str]) -> Dict[str, Any]:
    """Extract entities and relationships with local spaCy-backed extractors."""
    from semantica.kg import GraphBuilder

    builder = GraphBuilder(resolve_conflicts=False)
    return builder.build(
        documents,
        ner_method="ml",
        extract_relations=True,
        relation_method="pattern",
    )


def to_nodes_edges(build_result: Dict[str, Any]) -> Dict[str, Any]:
    """Translate GraphBuilder's vocabulary into ContextGraph's nodes/edges."""
    nodes = []
    for entity in build_result.get("entities", []):
        nodes.append(
            {
                "id": entity.get("id") or entity.get("text"),
                "type": entity.get("type"),
                "content": entity.get("text") or entity.get("id"),
                "metadata": {
                    "confidence": entity.get("confidence", 1.0),
                },
            }
        )
    edges = []
    for rel in build_result.get("relationships", []):
        edges.append(
            {
                "source": rel.get("source"),
                "target": rel.get("target"),
                "type": rel.get("type"),
                "weight": rel.get("weight", 1.0),
            }
        )
    return {"nodes": nodes, "edges": edges}


def documents_to_payload(
    documents: List[Dict[str, str]], application_id: str
) -> Dict[str, Any]:
    build_result = extract([item["text"] for item in documents])
    return to_nodes_edges(scope_build_result(build_result, application_id))
