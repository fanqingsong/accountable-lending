"""Prefect Server HTTP client — no lending_prefect import."""

import json
import re
from pathlib import Path

import backend.prefect_api as prefect_api


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_submit_application_run_posts_create_flow_run(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(request, timeout=30):
        calls.append((request.get_method(), request.full_url, request.data))
        if request.full_url.endswith("/deployments/name/application-flow/lending-application"):
            return FakeResponse({"id": "dep-1"})
        if request.full_url.endswith("/deployments/dep-1/create_flow_run"):
            return FakeResponse(
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "parameters": {"application_id": "harbor-bakery"},
                    "state": {"name": "Scheduled"},
                }
            )
        raise AssertionError(request.full_url)

    monkeypatch.setenv("PREFECT_API_URL", "http://prefect.example/api")
    monkeypatch.setattr(prefect_api.urllib.request, "urlopen", fake_urlopen)

    body = prefect_api.submit_application_run(
        application_id="harbor-bakery",
        applicant_name="Harbor",
        paths=[str(tmp_path / "a.txt")],
        snapshot_path=str(tmp_path / "g.json"),
        index_vectors=False,
    )
    assert body["flow_run_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["status"] == "SCHEDULED"
    assert any(method == "POST" and "create_flow_run" in url for method, url, _ in calls)


def test_read_application_job_merges_disk_result(monkeypatch, tmp_path):
    run_id = "22222222-2222-2222-2222-222222222222"
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / f"{run_id}.json").write_text(
        json.dumps({"decisions": {"final_decision": "d1"}, "entity_count": 3}),
        encoding="utf-8",
    )
    monkeypatch.setattr(prefect_api, "JOBS_DIR", jobs)
    monkeypatch.setenv("PREFECT_API_URL", "http://prefect.example/api")

    def fake_urlopen(request, timeout=30):
        return FakeResponse(
            {
                "id": run_id,
                "parameters": {
                    "application_id": "harbor-bakery",
                    "applicant_name": "Harbor",
                },
                "state": {"name": "Completed"},
            }
        )

    monkeypatch.setattr(prefect_api.urllib.request, "urlopen", fake_urlopen)
    body = prefect_api.read_application_job(run_id)
    assert body["status"] == "COMPLETED"
    assert body["decisions"]["final_decision"] == "d1"
    assert body["entity_count"] == 3


def test_backend_modules_do_not_import_lending_prefect():
    root = Path(__file__).resolve().parent.parent / "backend"
    offenders = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^(from|import) lending_prefect\b", text, re.M):
            offenders.append(path.name)
    assert offenders == []
