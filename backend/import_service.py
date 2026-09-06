"""Save uploaded applicant files and run the scoped lending pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from backend.pipeline import (
    ALLOWED_SUFFIXES,
    GRAPH_JSON,
    apply_case,
    list_applications,
    slugify,
    write_graph_snapshot,
)

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "exports" / "uploads"


class LendingImportError(ValueError):
    """User-facing import failure."""


def safe_filename(name: str) -> str:
    filename = Path(name or "").name
    if filename in {"", ".", ".."}:
        raise LendingImportError("invalid filename")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise LendingImportError(f"unsupported file type: {suffix or '(none)'}")
    return filename


def _existing_application_ids(graph) -> set[str]:
    found = set()
    for item in list_applications(graph):
        app_id = item.get("application_id") or ""
        if app_id:
            found.add(str(app_id))
        node_id = str(item.get("id") or "")
        if node_id.endswith("::application"):
            found.add(node_id[: -len("::application")])
    return found


def import_application(
    graph,
    files: List[Dict[str, Any]],
    applicant_name: str,
    application_id: str = "",
    high_risk: bool = False,
    thin_credit: bool = False,
    session=None,
    vector_store=None,
) -> Dict[str, Any]:
    """``files`` items are ``{"filename": str, "content": bytes}``."""
    applicant_name = (applicant_name or "").strip()
    if not applicant_name:
        raise LendingImportError("applicant_name is required")
    if not files:
        raise LendingImportError("at least one file is required")

    application_id = slugify(application_id or applicant_name)
    if application_id in _existing_application_ids(graph):
        raise LendingImportError(f"application already exists: {application_id}")

    dest = UPLOADS / application_id
    dest.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for item in files:
        filename = safe_filename(item.get("filename") or "")
        path = dest / filename
        path.write_bytes(item["content"])
        paths.append(path)

    result = apply_case(
        graph,
        paths=paths,
        application_id=application_id,
        applicant_name=applicant_name,
        high_risk=high_risk,
        thin_credit=thin_credit,
    )

    from backend.ontology import validate_graph

    report = validate_graph(graph, application_id=application_id)
    result["schema"] = report
    if not report["conforms"]:
        detail = "; ".join(item["message"] for item in report["violations"][:5])
        raise LendingImportError(f"schema validation failed: {detail}")

    write_graph_snapshot(graph, GRAPH_JSON)

    from backend.stores import persist_graph

    persisted = persist_graph(graph)
    result["persisted"] = persisted

    if vector_store is not None:
        from backend.retrieve import index_graph

        result["indexed"] = index_graph(graph, vector_store)
    if session is not None and hasattr(session, "rebuild_search_index"):
        session.rebuild_search_index()
    return result
