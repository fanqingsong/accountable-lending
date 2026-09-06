"""GraphRAG retrieve: keyword + optional Qdrant, then expand on the ContextGraph.

No LLM. The answer to "why manual review?" is the chunks, entities, and
CAUSED decision chain — not a generated paragraph.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UPLOADS = ROOT / "exports" / "uploads"

# Query language only — not Application ids. Case membership comes from
# Application nodes and `{application_id}::` prefixes (ADR-0004).
QUERY_ALIASES = {
    "转人工": "manual review referred_to_manual_review Policy 7.3 concentration 38%",
    "人工": "manual review referred",
    "为什么": "why outcome reasoning risk",
    "高风险": "high risk concentration 38%",
}

DECISION_CATEGORIES = ("risk_classification", "policy_check", "final_decision")
CAUSED_TYPE = "CAUSED"


def expand_query(query: str) -> str:
    extra = []
    lowered = query.lower()
    for needle, expansion in QUERY_ALIASES.items():
        if needle.lower() in lowered:
            extra.append(expansion)
    return " ".join([query] + extra).strip()


def query_terms(query: str) -> List[str]:
    expanded = expand_query(query)
    terms: List[str] = []
    for part in re.split(r"\s+", expanded.lower()):
        if len(part) > 1 and part not in terms:
            terms.append(part)
        for sub in re.split(r"[-_]+", part):
            if len(sub) > 1 and sub not in terms:
                terms.append(sub)
    return terms


def _metadata(node: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for key in ("properties", "metadata"):
        extra = node.get(key)
        if isinstance(extra, dict):
            merged.update(extra)
    return merged


def application_id_of(node: Dict[str, Any], mapping: Dict[str, str] | None = None) -> str:
    meta = _metadata(node)
    app_id = meta.get("application_id")
    if app_id:
        return str(app_id)
    node_id = str(node.get("id") or "")
    if mapping and node_id in mapping:
        return mapping[node_id]
    if "::" in node_id and not node_id.startswith("http"):
        prefix = node_id.split("::", 1)[0]
        if prefix and prefix not in {"decision", "entity"}:
            return prefix
    return ""


def application_map(graph) -> Dict[str, str]:
    """Map member node ids to an application_id via HAS_DECISION / CONTAINS."""
    nodes, edges = _nodes_edges(graph)
    apps: Dict[str, str] = {}
    for node in nodes:
        if str(node.get("type") or "") != "Application":
            continue
        node_id = str(node.get("id") or "")
        apps[node_id] = application_id_of(node) or (node_id.split("::", 1)[0] if "::" in node_id else node_id)
    mapping = dict(apps)
    for edge in edges:
        if str(edge.get("type") or "").upper() not in {"HAS_DECISION", "HAS_DOCUMENT", "CONTAINS"}:
            continue
        source = str(edge.get("source") or edge.get("source_id") or "")
        target = str(edge.get("target") or edge.get("target_id") or "")
        if source in apps and target:
            mapping[target] = apps[source]
    return mapping


def hinted_applications(graph, query: str) -> List[str]:
    """Resolve Application hints from the graph, not a baked-in case list."""
    expanded = expand_query(query).lower()
    hints = []
    nodes, _ = _nodes_edges(graph)
    for node in nodes:
        if str(node.get("type") or "") != "Application":
            continue
        app_id = application_id_of(node)
        if not app_id:
            continue
        tokens = [app_id.lower(), *app_id.lower().split("-")]
        content = str(node.get("content") or _metadata(node).get("content") or "")
        tokens.extend(re.split(r"\s+", content.lower()))
        if any(token in expanded for token in tokens if len(token) > 2):
            if app_id not in hints:
                hints.append(app_id)
    return hints


def node_text(node: Dict[str, Any]) -> str:
    meta = _metadata(node)
    parts = [
        node.get("content") or meta.get("content"),
        meta.get("body"),
        meta.get("category"),
        meta.get("outcome"),
        meta.get("reasoning"),
        meta.get("scenario"),
        meta.get("text"),
    ]
    body = document_body(node)
    if body:
        parts.append(body)
    return " ".join(str(part) for part in parts if part)


def document_body(node: Dict[str, Any]) -> str:
    if (node.get("type") or "") != "Document":
        return ""
    meta = _metadata(node)
    if meta.get("body"):
        return str(meta["body"])
    name = str(node.get("content") or "")
    app_id = application_id_of(node)
    for candidate in (
        UPLOADS / app_id / name if app_id else None,
        DATA_DIR / name,
    ):
        if candidate is not None and candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def score_text(text: str, terms: List[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _nodes_edges(graph) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = graph.to_dict() if hasattr(graph, "to_dict") else {}
    return list(data.get("nodes") or []), list(data.get("edges") or [])


def keyword_hits(graph, terms: List[str], limit: int = 8, mapping: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
    nodes, _ = _nodes_edges(graph)
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
    nodes, _ = _nodes_edges(graph)
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


def _merge_hits(primary: List[Dict[str, Any]], extra: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for hit in primary + extra:
        key = str(hit.get("id") or hit.get("text"))
        current = by_id.get(key)
        if current is None or hit["score"] > current["score"]:
            by_id[key] = hit
    merged = sorted(by_id.values(), key=lambda item: item["score"], reverse=True)
    return merged[:limit]


def related_decisions(graph, application_ids: List[str], mapping: Dict[str, str] | None = None) -> Dict[str, Any]:
    nodes, edges = _nodes_edges(graph)
    wanted = set(application_ids)
    decisions = []
    for node in nodes:
        if str(node.get("type") or "") != "decision":
            continue
        app_id = application_id_of(node, mapping)
        if wanted and app_id not in wanted:
            continue
        meta = _metadata(node)
        decisions.append(
            {
                "id": node.get("id"),
                "category": meta.get("category"),
                "outcome": meta.get("outcome"),
                "scenario": node.get("content") or meta.get("scenario"),
                "reasoning": meta.get("reasoning"),
                "application_id": app_id,
            }
        )
    order = {category: index for index, category in enumerate(DECISION_CATEGORIES)}
    decisions.sort(key=lambda item: order.get(str(item.get("category") or ""), 9))
    caused = [
        {
            "from": edge.get("source") or edge.get("source_id"),
            "to": edge.get("target") or edge.get("target_id"),
        }
        for edge in edges
        if str(edge.get("type") or "") == CAUSED_TYPE
    ]
    decision_ids = {item["id"] for item in decisions}
    return {
        "decisions": decisions,
        "caused": [
            link
            for link in caused
            if link["from"] in decision_ids and link["to"] in decision_ids
        ],
    }


def document_hits_for_applications(
    graph, application_ids: List[str], mapping: Dict[str, str] | None = None
) -> List[Dict[str, Any]]:
    """Return Document chunks for named Applications even when the query is only an id."""
    wanted = set(application_ids)
    if not wanted:
        return []
    nodes, _ = _nodes_edges(graph)
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


def related_entities(graph, application_ids: List[str], terms: List[str], limit: int = 12, mapping: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
    nodes, _ = _nodes_edges(graph)
    wanted = set(application_ids)
    scored = []
    for node in nodes:
        ntype = str(node.get("type") or "")
        if ntype in {"Document", "decision", "Application", "category", "decision_maker"}:
            continue
        app_id = application_id_of(node, mapping)
        if wanted and app_id not in wanted:
            continue
        text = str(node.get("content") or node.get("id") or "")
        display = text.split("::", 1)[-1] if "::" in text else text
        score = score_text(display, terms)
        if score <= 0 and not wanted:
            continue
        scored.append(
            {
                "id": node.get("id"),
                "type": ntype,
                "text": display,
                "score": score,
                "application_id": app_id,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def retrieve(graph, query: str, store=None, limit: int = 8) -> Dict[str, Any]:
    """Return chunks, entities, and the causal decision chain. No generation."""
    query = (query or "").strip()
    if not query:
        return {"query": "", "chunks": [], "entities": [], "decisions": [], "caused": []}

    terms = query_terms(query)
    mapping = application_map(graph)
    chunks = _merge_hits(
        keyword_hits(graph, terms, limit=limit, mapping=mapping),
        vector_hits(store, expand_query(query), limit=limit),
        limit,
    )
    hinted = hinted_applications(graph, query)
    if hinted:
        chunks = _merge_hits(
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
