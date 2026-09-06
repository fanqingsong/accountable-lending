"""HTTP client for Prefect Server. Does not import lending_prefect or flow code."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from backend.application import (
    DATA_DIR,
    GRAPH_JSON,
    SEED_APPLICANT_NAME,
    SEED_APPLICATION_ID,
    load_policy_facts,
)

APPLICATION_FLOW = "application-flow"
APPLICATION_DEPLOYMENT = "lending-application"
JOBS_DIR = GRAPH_JSON.parent / "jobs"


class PrefectAPIError(RuntimeError):
    """Prefect Server rejected or could not complete a request."""


def prefect_api_url() -> str:
    return os.environ.get("PREFECT_API_URL", "").strip().rstrip("/")


def job_result_path(flow_run_id: str, snapshot_path: Optional[Path] = None) -> Path:
    root = Path(snapshot_path).parent if snapshot_path is not None else JOBS_DIR.parent
    if snapshot_path is None:
        return JOBS_DIR / f"{flow_run_id}.json"
    return root / "jobs" / f"{flow_run_id}.json"


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = prefect_api_url()
    if not base:
        raise PrefectAPIError("PREFECT_API_URL is not set")
    url = f"{base}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PrefectAPIError(f"{method} {path} failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise PrefectAPIError(f"{method} {path} failed: {exc.reason}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise PrefectAPIError(f"{method} {path} returned a non-object")
    return parsed


def _state_name(run: Dict[str, Any]) -> str:
    state = run.get("state") or {}
    return str(state.get("name") or state.get("type") or "UNKNOWN").upper()


def _run_id(run: Dict[str, Any]) -> str:
    return str(run.get("id") or "")


def resolve_deployment(flow_name: str, deployment_name: str) -> Dict[str, Any]:
    return _request("GET", f"/deployments/name/{flow_name}/{deployment_name}")


def create_flow_run(
    flow_name: str,
    deployment_name: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            deployment = resolve_deployment(flow_name, deployment_name)
            deployment_id = deployment.get("id")
            if not deployment_id:
                raise PrefectAPIError("deployment response missing id")
            return _request(
                "POST",
                f"/deployments/{deployment_id}/create_flow_run",
                {"parameters": parameters},
            )
        except PrefectAPIError as exc:
            last_error = exc
            time.sleep(2)
    raise PrefectAPIError(f"could not submit {flow_name}/{deployment_name}: {last_error}")


def read_flow_run(flow_run_id: str) -> Dict[str, Any]:
    UUID(flow_run_id)
    return _request("GET", f"/flow_runs/{flow_run_id}")


def wait_for_flow_run(flow_run_id: str, timeout: float = 600) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = read_flow_run(flow_run_id)
        name = _state_name(run)
        if name in {"COMPLETED", "FAILED", "CRASHED", "CANCELLED"}:
            return run
        time.sleep(2)
    raise PrefectAPIError(f"flow run {flow_run_id} did not finish in time")


def _result_from_disk(flow_run_id: str) -> Dict[str, Any]:
    path = job_result_path(flow_run_id)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _job_body(run: Dict[str, Any]) -> Dict[str, Any]:
    params = run.get("parameters") or {}
    flow_run_id = _run_id(run)
    status = _state_name(run)
    body: Dict[str, Any] = {
        "flow_run_id": flow_run_id,
        "status": status,
        "application_id": params.get("application_id"),
        "applicant_name": params.get("applicant_name"),
    }
    if status == "COMPLETED":
        body.update(_result_from_disk(flow_run_id))
    if status in {"FAILED", "CRASHED", "CANCELLED"}:
        state = run.get("state") or {}
        body["error"] = str(state.get("message") or status)
    return body


def submit_application_run(
    application_id: str,
    applicant_name: str,
    paths: list[str],
    policy_facts: Optional[Dict[str, Any]] = None,
    snapshot_path: Optional[str] = None,
    index_vectors: bool = True,
    wait: bool = False,
) -> Dict[str, Any]:
    parameters = {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "paths": [str(path) for path in paths],
        "policy_facts": policy_facts,
        "snapshot_path": snapshot_path or str(GRAPH_JSON),
        "index_vectors": index_vectors,
    }
    run = create_flow_run(APPLICATION_FLOW, APPLICATION_DEPLOYMENT, parameters)
    if wait:
        run = wait_for_flow_run(_run_id(run))
    return _job_body(run)


def submit_seed_run(snapshot_path: Optional[str] = None, wait: bool = True) -> Dict[str, Any]:
    dest = snapshot_path or str(GRAPH_JSON)
    paths = [str(path) for path in sorted(DATA_DIR.glob("*.txt"))]
    return submit_application_run(
        application_id=SEED_APPLICATION_ID,
        applicant_name=SEED_APPLICANT_NAME,
        paths=paths,
        policy_facts=load_policy_facts([Path(path) for path in paths]),
        snapshot_path=dest,
        index_vectors=True,
        wait=wait,
    )


def read_application_job(flow_run_id: str) -> Dict[str, Any]:
    try:
        run = read_flow_run(flow_run_id)
    except (PrefectAPIError, ValueError) as exc:
        return {"flow_run_id": flow_run_id, "status": "UNKNOWN", "error": str(exc)}
    return _job_body(run)
