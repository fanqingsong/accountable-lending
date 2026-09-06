"""Save uploaded applicant files and submit application_flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.application import (
    ALLOWED_SUFFIXES,
    GRAPH_JSON,
    POLICY_FACTS_FILENAME,
    existing_application_ids,
    normalize_policy_facts,
    slugify,
)
from backend.paths import UPLOADS


class LendingImportError(ValueError):
    """User-facing import failure."""


def safe_filename(name: str) -> str:
    filename = Path(name or "").name
    if filename in {"", ".", ".."}:
        raise LendingImportError("invalid filename")
    suffix = Path(filename).suffix.lower()
    if filename == POLICY_FACTS_FILENAME:
        return filename
    if suffix not in ALLOWED_SUFFIXES:
        raise LendingImportError(f"unsupported file type: {suffix or '(none)'}")
    return filename


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
    if application_id in existing_application_ids(graph):
        raise LendingImportError(f"application already exists: {application_id}")

    dest = UPLOADS / application_id
    dest.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    uploaded_facts = None
    for item in files:
        filename = safe_filename(item.get("filename") or "")
        path = dest / filename
        path.write_bytes(item["content"])
        paths.append(path)
        if filename == POLICY_FACTS_FILENAME:
            try:
                payload = json.loads(item["content"].decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LendingImportError(f"invalid {POLICY_FACTS_FILENAME}: {exc}") from exc
            if not isinstance(payload, dict):
                raise LendingImportError(f"{POLICY_FACTS_FILENAME} must be a JSON object")
            uploaded_facts = normalize_policy_facts(payload)

    if uploaded_facts is None:
        uploaded_facts = normalize_policy_facts(
            {"high_risk": high_risk, "thin_credit": thin_credit}
        )

    from backend.prefect_api import PrefectAPIError, submit_application_run

    try:
        return submit_application_run(
            application_id=application_id,
            applicant_name=applicant_name,
            paths=[str(path) for path in paths],
            policy_facts=uploaded_facts,
            snapshot_path=str(GRAPH_JSON),
            index_vectors=vector_store is not None,
        )
    except (ValueError, PrefectAPIError) as exc:
        raise LendingImportError(str(exc)) from exc
