"""GraphRAG retrieve: keyword + optional Qdrant, then expand on the ContextGraph.

No LLM. The answer to "why manual review?" is the chunks, entities, and
CAUSED decision chain — not a generated paragraph.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.retrieve.audit_trail import DECISION_CATEGORIES, related_decisions, related_entities
from backend.retrieve.membership import application_map, hinted_applications
from backend.retrieve.query import expand_query, query_terms
from backend.retrieve.search import (
    connect_vector_store,
    document_hits_for_applications,
    index_graph,
    keyword_hits,
    merge_hits,
    vector_hits,
)
from backend.retrieve.text import score_text

__all__ = [
    "DECISION_CATEGORIES",
    "connect_vector_store",
    "expand_query",
    "hinted_applications",
    "index_graph",
    "query_terms",
    "retrieve",
    "score_text",
]


def retrieve(graph, query: str, store=None, limit: int = 8) -> Dict[str, Any]:
    """Return chunks, entities, and the causal decision chain. No generation."""
    query = (query or "").strip()
    if not query:
        return {"query": "", "chunks": [], "entities": [], "decisions": [], "caused": []}

    terms = query_terms(query)
    mapping = application_map(graph)
    chunks = merge_hits(
        keyword_hits(graph, terms, limit=limit, mapping=mapping),
        vector_hits(store, expand_query(query), limit=limit),
        limit,
    )
    hinted = hinted_applications(graph, query)
    if hinted:
        chunks = merge_hits(
            chunks,
            document_hits_for_applications(graph, hinted, mapping),
            limit,
        )
    app_ids = list(hinted)
    if not app_ids:
        for hit in chunks:
            app_id = hit.get("application_id") or mapping.get(str(hit.get("id") or ""), "")
            if app_id and app_id not in app_ids:
                app_ids.append(app_id)
    if hinted:
        chunks = [
            hit
            for hit in chunks
            if (hit.get("application_id") or mapping.get(str(hit.get("id") or ""), "")) in hinted
            or not (hit.get("application_id") or mapping.get(str(hit.get("id") or ""), ""))
        ]
        for hit in chunks:
            if not hit.get("application_id"):
                hit["application_id"] = mapping.get(str(hit.get("id") or ""), "")
    related = related_decisions(graph, app_ids, mapping)
    return {
        "query": query,
        "expanded_query": expand_query(query),
        "chunks": chunks,
        "entities": related_entities(graph, app_ids, terms, mapping=mapping),
        "decisions": related["decisions"],
        "caused": related["caused"],
    }
