"""Lending HTTP contract: JSON APIs only."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.import_service import LendingImportError
from backend.routes import attach_lending_routes


class FakeGraph:
    def to_dict(self):
        return {
            "nodes": [
                {
                    "id": "sunrise-coffee::application",
                    "type": "Application",
                    "content": "Sunrise Coffee Roasters LLC",
                    "metadata": {"application_id": "sunrise-coffee"},
                }
            ],
            "edges": [],
        }


class FakeSession:
    def __init__(self, graph):
        self.graph = graph


def _client(monkeypatch, retrieve_payload=None, answer_payload=None, import_fn=None):
    monkeypatch.setattr(
        "backend.routes.retrieve",
        lambda graph, query, store=None: retrieve_payload
        or {"query": query, "chunks": [], "decisions": [], "caused": [], "entities": []},
    )
    monkeypatch.setattr(
        "backend.routes.answer",
        lambda graph, query, store=None: answer_payload
        or {
            "query": query,
            "answer": "根据图谱，决策链为：final_decision=referred_to_manual_review。",
            "source": "extractive",
            "chunks": [],
            "decisions": [],
            "caused": [],
            "entities": [],
        },
    )
    if import_fn is not None:
        monkeypatch.setattr("backend.routes.import_application", import_fn)

    app = FastAPI()
    attach_lending_routes(app, FakeSession(FakeGraph()))
    return TestClient(app)


def test_api_app_does_not_serve_lending_html(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/lending").status_code == 404
    assert client.get("/lending/retrieve").status_code == 404
    assert client.get("/lending/chat").status_code == 404
    assert client.get("/lending/ontology").status_code == 404


def test_applications_api_is_json(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/lending/applications")
    assert response.status_code == 200
    assert response.json()["applications"][0]["application_id"] == "sunrise-coffee"


def test_import_api_returns_json_success(monkeypatch):
    def fake_import(*args, **kwargs):
        return {
            "application_id": "harbor-bakery",
            "applicant_name": "Harbor Bakehouse Pvt Ltd",
            "entity_count": 2,
            "decisions": {"final_decision": "d1"},
        }

    client = _client(monkeypatch, import_fn=fake_import)
    response = client.post(
        "/api/lending/import",
        data={"applicant_name": "Harbor Bakehouse Pvt Ltd"},
        files={"files": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["application_id"] == "harbor-bakery"
    assert "error" not in body
    assert "<html" not in response.text.lower()


def test_import_api_returns_json_error(monkeypatch):
    def fake_import(*args, **kwargs):
        raise LendingImportError("application already exists: harbor-bakery")

    client = _client(monkeypatch, import_fn=fake_import)
    response = client.post(
        "/api/lending/import",
        data={"applicant_name": "Harbor Bakehouse Pvt Ltd"},
        files={"files": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json() == {"error": "application already exists: harbor-bakery"}


def test_import_job_reloads_graph_when_completed(monkeypatch):
    class ReloadSession:
        def __init__(self, graph):
            self.graph = graph
            self.reloads = 0

        def reload_graph(self):
            self.reloads += 1

    session = ReloadSession(FakeGraph())
    monkeypatch.setattr(
        "backend.routes.read_application_job",
        lambda flow_run_id: {
            "flow_run_id": flow_run_id,
            "status": "COMPLETED",
            "application_id": "harbor-bakery",
            "decisions": {"final_decision": "d1"},
        },
    )
    monkeypatch.setattr(
        "backend.routes.retrieve",
        lambda graph, query, store=None: {
            "query": query,
            "chunks": [],
            "decisions": [],
            "caused": [],
            "entities": [],
        },
    )
    monkeypatch.setattr(
        "backend.routes.answer",
        lambda graph, query, store=None: {"query": query, "answer": "x", "source": "extractive"},
    )
    app = FastAPI()
    attach_lending_routes(app, session)
    client = TestClient(app)
    response = client.get("/api/lending/jobs/run-1")
    assert response.status_code == 200
    assert response.json()["application_id"] == "harbor-bakery"
    assert session.reloads == 1


def test_retrieve_and_chat_apis_are_json(monkeypatch):
    client = _client(
        monkeypatch,
        retrieve_payload={
            "query": "为什么转人工",
            "chunks": [{"kind": "Document", "text": "Thin credit history.", "application_id": "sunrise-coffee"}],
            "decisions": [
                {"category": "risk_classification", "outcome": "high_risk"},
                {"category": "policy_check", "outcome": "manual_review_required"},
                {"category": "final_decision", "outcome": "referred_to_manual_review"},
            ],
            "caused": [{"from": "d-risk", "to": "d-policy"}],
            "entities": [],
        },
    )
    retrieve = client.post("/api/lending/retrieve", json={"query": "为什么转人工"})
    assert retrieve.status_code == 200
    assert retrieve.json()["decisions"][2]["category"] == "final_decision"
    assert retrieve.json()["chunks"][0]["text"].startswith("Thin credit")

    chat = client.post("/api/lending/chat", json={"query": "为什么转人工"})
    assert chat.status_code == 200
    assert "final_decision" in chat.json()["answer"]


def test_cors_allows_lending_ui_origin(monkeypatch):
    client = _client(monkeypatch)
    origin = "http://localhost:8080"
    preflight = client.options(
        "/api/lending/applications",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.headers.get("access-control-allow-origin") == origin

    response = client.get("/api/lending/applications", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.json()["applications"][0]["application_id"] == "sunrise-coffee"


def test_ui_files_use_configurable_api_and_explorer_urls():
    root = Path(__file__).resolve().parent.parent / "frontend" / "lending"
    api = (root / "src" / "api.ts").read_text(encoding="utf-8")
    assert "VITE_LENDING_API_BASE" in api
    assert "VITE_LENDING_EXPLORER_URL" in api
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "VITE_LENDING_API_BASE" in dockerfile
    main = (root / "src" / "main.tsx").read_text(encoding="utf-8")
    assert 'basename="/lending"' in main
    assert "{{applications}}" not in api
    assert "{{results}}" not in api


def test_api_module_does_not_construct_explorer():
    text = Path(__file__).resolve().parent.parent.joinpath("backend", "api.py").read_text(
        encoding="utf-8"
    )
    assert "create_app" not in text
    assert "semantica.explorer" not in text
    assert "attach_lending_routes" in text


def test_explorer_entry_does_not_attach_lending_routes():
    text = Path(__file__).resolve().parent.parent.joinpath("backend", "admin.py").read_text(
        encoding="utf-8"
    )
    assert "attach_lending_routes" not in text
    assert "load_snapshot_session" in text


def test_ontology_api_includes_validation(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/lending/ontology")
    assert response.status_code == 200
    body = response.json()
    assert "ontology" in body
    assert "validation" in body
    assert "shacl" in body
    assert "classes" in body["ontology"]
    assert "relationships" in body["ontology"]
