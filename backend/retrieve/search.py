"""Keyword and optional Qdrant hits. No generation."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from backend.context_graph import nodes_and_edges
from backend.retrieve.membership import application_id_of
from backend.retrieve.text import node_text, score_text


def keyword_hits(
    graph, terms: List[str], limit: int = 8, mapping: Dict[str, str] | None = None
) -> List[Dict[str, Any]]:
    nodes, _ = nodes_and_edges(graph)
    scored = []
    for node in nodes:
        ntype = str(node.get("type") or "")
        if ntype not in {"Document", "decision", "Application"}:
            continue
        text = node_text(node)
        score = score_text(text, terms)
        if score <= 0:
            continue
        scored.append(
            {
                "id": node.get("id"),
                "kind": ntype,
                "text": text[:800],
                "score": float(score),
                "source": "keyword",
                "application_id": application_id_of(node, mapping),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def connect_vector_store():
    url = os.environ.get("QDRANT_URL", "").strip()
    if not url:
        return None
    try:
        import qdrant_client  # noqa: F401
    except ImportError:
        return None
    from semantica.vector_store import VectorStore

    store = VectorStore(
        backend="qdrant",
        url=url,
        collection_name=os.environ.get("QDRANT_COLLECTION", "lending"),
        dimension=int(os.environ.get("QDRANT_DIMENSION", "384")),
    )
    return store


def indexable_records(graph) -> List[Dict[str, Any]]:
    nodes, _ = nodes_and_edges(graph)
    records = []
    for node in nodes:
        ntype = str(node.get("type") or "")
        if ntype not in {"Document", "decision"}:
            continue
        text = node_text(node).strip()
        if not text:
            continue
        records.append(
            {
                "id": str(node.get("id")),
                "text": text,
                "metadata": {
                    "kind": ntype,
                    "application_id": application_id_of(node),
                },
            }
        )
    return records


def index_graph(graph, store) -> int:
    records = indexable_records(graph)
    if not records or store is None:
        return 0
    store.add_documents(
        documents=[item["text"] for item in records],
        metadata=[item["metadata"] | {"node_id": item["id"]} for item in records],
    )
    return len(records)


def vector_hits(store, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if store is None:
        return []
    try:
        raw = store.search(query, limit=limit)
    except TypeError:
        try:
            raw = store.search(query)
        except Exception:
            return []
    except Exception:
        return []
    hits = []
    for item in raw or []:
        if isinstance(item, dict):
            meta = item.get("metadata") or {}
            hits.append(
                {
                    "id": meta.get("node_id") or item.get("id"),
                    "kind": meta.get("kind") or "chunk",
                    "text": str(item.get("content") or item.get("text") or "")[:800],
                    "score": float(item.get("score") or 0),
                    "source": "vector",
                    "application_id": meta.get("application_id") or "",
                }
            )
    return hits


def merge_hits(
    primary: List[Dict[str, Any]], extra: List[Dict[str, Any]], limit: int
) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for hit in primary + extra:
        key = str(hit.get("id") or hit.get("text"))
        current = by_id.get(key)
        if current is None or hit["score"] > current["score"]:
            by_id[key] = hit
    merged = sorted(by_id.values(), key=lambda item: item["score"], reverse=True)
    return merged[:limit]


def document_hits_for_applications(
    graph, application_ids: List[str], mapping: Dict[str, str] | None = None
) -> List[Dict[str, Any]]:
    """Return Document chunks for named Applications even when the query is only an id."""
    wanted = set(application_ids)
    if not wanted:
        return []
    nodes, _ = nodes_and_edges(graph)
    hits = []
    for node in nodes:
        if str(node.get("type") or "") != "Document":
            continue
        app_id = application_id_of(node, mapping)
        if app_id not in wanted:
            continue
        text = node_text(node)
        if not text.strip():
            continue
        hits.append(
            {
                "id": node.get("id"),
                "kind": "Document",
                "text": text[:800],
                "score": 1.0,
                "source": "application",
                "application_id": app_id,
            }
        )
    return hits
