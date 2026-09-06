"""Document / node text used by keyword retrieve."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.context_graph import node_properties
from backend.paths import DATA_DIR, UPLOADS
from backend.retrieve.membership import application_id_of


def node_text(node: Dict[str, Any]) -> str:
    meta = node_properties(node)
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
    meta = node_properties(node)
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
