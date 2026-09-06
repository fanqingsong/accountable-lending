"""Prefect adapter: compose Application assembly from Application leaves."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from prefect import flow, task

from backend.application import (
    DATA_DIR,
    GRAPH_JSON,
    SEED_APPLICANT_NAME,
    SEED_APPLICATION_ID,
    existing_application_ids,
    load_graph,
    load_policy_facts,
    normalize_policy_facts,
)
from lending_prefect.attach import apply_payload
from lending_prefect.decide import record_decision_chain
from lending_prefect.ingest import documents_to_payload, ingest_files
from lending_prefect.snapshot import write_graph_snapshot

APPLICATION_DEPLOYMENT = "application-flow/lending-application"

_LOCAL_JOBS: Dict[str, Dict[str, Any]] = {}


def prefect_api_configured() -> bool:
    return bool(os.environ.get("PREFECT_API_URL", "").strip())


def seed_parameters(snapshot_path: Optional[str] = None) -> Dict[str, Any]:
    paths = [str(path) for path in sorted(DATA_DIR.glob("*.txt"))]
    return {
        "application_id": SEED_APPLICATION_ID,
        "applicant_name": SEED_APPLICANT_NAME,
        "paths": paths,
        "policy_facts": load_policy_facts([Path(path) for path in paths]),
        "snapshot_path": snapshot_path or str(GRAPH_JSON),
        "index_vectors": True,
    }


def _work_path(snapshot: Path, application_id: str) -> Path:
    return snapshot.with_name(f"{snapshot.name}.{application_id}.work")


def _prepare_work_copy(snapshot: Path, work: Path) -> None:
    work.parent.mkdir(parents=True, exist_ok=True)
    if work.is_file():
        work.unlink()
    if snapshot.is_file():
        shutil.copy2(snapshot, work)


@task
def ingest_task(paths: List[str]) -> List[Dict[str, str]]:
    return ingest_files([Path(path) for path in paths])


@task
def extract_task(documents: List[Dict[str, str]], application_id: str) -> Dict[str, Any]:
    return documents_to_payload(documents, application_id)


@task
def attach_task(
    work_path: str,
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, str]],
    payload: Dict[str, Any],
    policy_facts: Dict[str, bool],
) -> List[str]:
    graph = load_graph(Path(work_path))
    if application_id in existing_application_ids(graph):
        raise ValueError(f"application already exists: {application_id}")
    entity_ids = apply_payload(
        graph,
        payload,
        application_id,
        applicant_name,
        documents,
        policy_facts=policy_facts,
    )
    write_graph_snapshot(graph, Path(work_path))
    return entity_ids


@task
def decide_task(
    work_path: str,
    application_id: str,
    applicant_name: str,
    entity_ids: List[str],
) -> Dict[str, str]:
    graph = load_graph(Path(work_path))
    decisions = record_decision_chain(
        graph,
        application_id,
        applicant=applicant_name,
        entity_ids=entity_ids[:6],
    )
    write_graph_snapshot(graph, Path(work_path))
    return decisions


@task
def validate_task(work_path: str, application_id: str) -> Dict[str, Any]:
    from backend.ontology import validate_graph

    graph = load_graph(Path(work_path))
    report = validate_graph(graph, application_id=application_id)
    if not report["conforms"]:
        detail = "; ".join(item["message"] for item in report["violations"][:5])
        raise ValueError(f"schema validation failed: {detail}")
    return report


@task
def persist_task(work_path: str, snapshot_path: str, index_vectors: bool) -> Dict[str, Any]:
    from backend.stores import persist_graph

    graph = load_graph(Path(work_path))
    write_graph_snapshot(graph, Path(snapshot_path))
    persisted = persist_graph(graph)
    indexed = None
    if index_vectors:
        from backend.retrieve import connect_vector_store, index_graph

        store = connect_vector_store()
        if store is not None:
            indexed = index_graph(graph, store)
    return {"persisted": persisted, "indexed": indexed}


@flow(name="application-flow")
def application_flow(
    application_id: str,
    applicant_name: str,
    paths: List[str],
    policy_facts: Optional[Dict[str, Any]] = None,
    snapshot_path: Optional[str] = None,
    index_vectors: bool = True,
) -> Dict[str, Any]:
    snapshot = Path(snapshot_path) if snapshot_path else GRAPH_JSON
    work = _work_path(snapshot, application_id)
    try:
        _prepare_work_copy(snapshot, work)
        facts = (
            normalize_policy_facts(policy_facts)
            if policy_facts is not None
            else load_policy_facts([Path(path) for path in paths])
        )
        documents = ingest_task(paths)
        payload = extract_task(documents, application_id)
        entity_ids = attach_task(
            str(work),
            application_id,
            applicant_name,
            documents,
            payload,
            facts,
        )
        decisions = decide_task(str(work), application_id, applicant_name, entity_ids)
        schema = validate_task(str(work), application_id)
        persisted = persist_task(str(work), str(snapshot), index_vectors)
        result = {
            "application_id": application_id,
            "applicant_name": applicant_name,
            "entity_count": len(entity_ids),
            "decisions": decisions,
            "document_names": [item["name"] for item in documents],
            "schema": schema,
            **persisted,
        }
        _write_job_result(result, snapshot)
        return result
    except Exception:
        if work.is_file() and work != snapshot:
            work.unlink(missing_ok=True)
        raise
    finally:
        if work.is_file() and work != snapshot:
            work.unlink(missing_ok=True)


def _write_job_result(result: Dict[str, Any], snapshot: Path) -> None:
    try:
        from prefect.runtime import flow_run

        run_id = getattr(flow_run, "id", None)
    except Exception:  # noqa: BLE001 — in-process tests may lack a server run
        run_id = None
    if not run_id:
        return
    from backend.prefect_api import job_result_path

    dest = job_result_path(str(run_id), snapshot)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result), encoding="utf-8")


def submit_application_run(
    application_id: str,
    applicant_name: str,
    paths: List[str],
    policy_facts: Optional[Dict[str, Any]] = None,
    snapshot_path: Optional[str] = None,
    index_vectors: bool = True,
    wait: bool = False,
) -> Dict[str, Any]:
    params = {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "paths": [str(path) for path in paths],
        "policy_facts": policy_facts,
        "snapshot_path": snapshot_path or str(GRAPH_JSON),
        "index_vectors": index_vectors,
    }
    if prefect_api_configured():
        import time

        from prefect.deployments import run_deployment

        flow_run = None
        last_error: Exception | None = None
        attempts = 30 if wait else 8
        for _ in range(attempts):
            try:
                flow_run = run_deployment(
                    name=APPLICATION_DEPLOYMENT,
                    parameters=params,
                    timeout=600 if wait else 0,
                )
                break
            except Exception as exc:  # noqa: BLE001 — wait for worker to serve
                last_error = exc
                time.sleep(2)
        if flow_run is None:
            raise RuntimeError(f"could not submit {APPLICATION_DEPLOYMENT}: {last_error}")
        status = getattr(getattr(flow_run, "state", None), "name", None) or "SCHEDULED"
        body: Dict[str, Any] = {
            "application_id": application_id,
            "applicant_name": applicant_name,
            "flow_run_id": str(flow_run.id),
            "status": str(status).upper(),
        }
        if wait and str(status).upper() == "COMPLETED":
            result = flow_run.state.result() if flow_run.state else {}
            if isinstance(result, dict):
                body.update(result)
        return body

    result = application_flow(**params)
    job_id = str(uuid.uuid4())
    body = {
        "flow_run_id": job_id,
        "status": "COMPLETED",
        **result,
    }
    _LOCAL_JOBS[job_id] = body
    return body


def read_application_job(flow_run_id: str) -> Dict[str, Any]:
    if flow_run_id in _LOCAL_JOBS:
        return dict(_LOCAL_JOBS[flow_run_id])
    if not prefect_api_configured():
        return {"flow_run_id": flow_run_id, "status": "UNKNOWN", "error": "unknown job"}
    from prefect.client.orchestration import get_client

    with get_client(sync_client=True) as client:
        run = client.read_flow_run(UUID(flow_run_id))
    state = run.state
    name = str(state.name).upper() if state is not None else "UNKNOWN"
    body: Dict[str, Any] = {"flow_run_id": flow_run_id, "status": name}
    if state is not None and state.is_completed():
        result = state.result()
        if isinstance(result, dict):
            body.update(result)
    if state is not None and (state.is_failed() or state.is_crashed()):
        body["error"] = str(state.message or name)
    return body
