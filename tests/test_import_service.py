"""Tests for upload validation and duplicate application rejection."""

import json

from backend.import_service import LendingImportError, import_application, safe_filename
from backend.pipeline import apply_payload, write_graph_snapshot


def test_safe_filename_rejects_bad_types_and_paths():
    assert safe_filename("notes.txt") == "notes.txt"
    try:
        safe_filename("../secret.pdf")
    except LendingImportError:
        raise AssertionError("basename should be allowed after Path.name")
    try:
        safe_filename("notes.exe")
        raise AssertionError("exe should be rejected")
    except LendingImportError as exc:
        assert "unsupported" in str(exc)


class FakeGraph:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.saved = None

    def add_node(self, node_id, node_type, content=None, **kwargs):
        self.nodes.append(
            {"id": node_id, "type": node_type, "content": content, "metadata": kwargs}
        )

    def add_edge(self, source, target, edge_type, weight=1.0, **kwargs):
        self.edges.append((source, target, edge_type))

    def to_dict(self):
        return {"nodes": self.nodes, "edges": list(self.edges)}

    def save_to_file(self, path):
        self.saved = path


def test_import_application_rejects_duplicate(tmp_path, monkeypatch):
    graph = FakeGraph()
    apply_payload(
        graph,
        {"nodes": [{"id": "harbor-bakery::A", "type": "ORG", "content": "H"}], "edges": []},
        "harbor-bakery",
        "Harbor Bakehouse Pvt Ltd",
        [],
    )

    snap = tmp_path / "g.json"
    snap.write_text('{"keep":true}', encoding="utf-8")
    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", snap)
    monkeypatch.setattr("backend.stores.persist_graph", lambda graph: {"skipped": True})

    try:
        import_application(
            graph,
            files=[{"filename": "a.txt", "content": b"hello"}],
            applicant_name="Harbor Bakehouse Pvt Ltd",
            application_id="harbor-bakery",
        )
        raise AssertionError("duplicate should fail")
    except LendingImportError as exc:
        assert "already exists" in str(exc)
    assert snap.read_text(encoding="utf-8") == '{"keep":true}'


def test_import_application_writes_files_and_calls_apply_case(tmp_path, monkeypatch):
    graph = FakeGraph()
    called = {}

    def fake_apply_case(graph, paths, application_id, applicant_name, high_risk, thin_credit):
        called["paths"] = [str(path) for path in paths]
        called["application_id"] = application_id
        called["high_risk"] = high_risk
        return {
            "application_id": application_id,
            "applicant_name": applicant_name,
            "entity_count": 2,
            "decisions": {"final_decision": "d1"},
            "document_names": ["a.txt"],
        }

    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", tmp_path / "g.json")
    monkeypatch.setattr("backend.import_service.apply_case", fake_apply_case)
    monkeypatch.setattr("backend.stores.persist_graph", lambda graph: {"skipped": True})

    result = import_application(
        graph,
        files=[{"filename": "a.txt", "content": b"hello"}],
        applicant_name="Harbor Bakehouse Pvt Ltd",
        high_risk=False,
        thin_credit=False,
    )
    assert result["application_id"] == "harbor-bakehouse-pvt-ltd"
    assert (tmp_path / "harbor-bakehouse-pvt-ltd" / "a.txt").read_bytes() == b"hello"
    assert called["high_risk"] is False
    assert (tmp_path / "g.json").is_file()


def test_import_writes_reloadable_snapshot_with_scoped_caused_chain(tmp_path, monkeypatch):
    graph = FakeGraph()
    snap = tmp_path / "lending_graph.json"

    def fake_apply_case(graph, paths, application_id, applicant_name, high_risk, thin_credit):
        graph.nodes = [
            {
                "id": f"{application_id}::application",
                "type": "Application",
                "content": applicant_name,
                "metadata": {"application_id": application_id},
            },
            {
                "id": f"{application_id}::d-risk",
                "type": "Decision",
                "metadata": {"category": "risk_classification", "outcome": "high_risk"},
            },
            {
                "id": f"{application_id}::d-policy",
                "type": "Decision",
                "metadata": {"category": "policy_check", "outcome": "manual_review_required"},
            },
            {
                "id": f"{application_id}::d-final",
                "type": "Decision",
                "metadata": {"category": "final_decision", "outcome": "referred_to_manual_review"},
            },
        ]
        graph.edges = [
            (f"{application_id}::d-risk", f"{application_id}::d-policy", "CAUSED"),
            (f"{application_id}::d-policy", f"{application_id}::d-final", "CAUSED"),
        ]
        return {
            "application_id": application_id,
            "applicant_name": applicant_name,
            "entity_count": 1,
            "decisions": {"final_decision": f"{application_id}::d-final"},
        }

    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", snap)
    monkeypatch.setattr("backend.import_service.apply_case", fake_apply_case)
    monkeypatch.setattr("backend.stores.persist_graph", lambda graph: {"skipped": True})
    monkeypatch.setattr(
        "backend.ontology.validate_graph",
        lambda graph, application_id=None: {"conforms": True, "violations": [], "checked": 4},
    )

    import_application(
        graph,
        files=[{"filename": "a.txt", "content": b"notes"}],
        applicant_name="Harbor Bakehouse Pvt Ltd",
        application_id="harbor-bakery",
    )
    loaded = json.loads(snap.read_text(encoding="utf-8"))
    ids = {node["id"] for node in loaded["nodes"]}
    assert "harbor-bakery::application" in ids
    assert all(node_id.startswith("harbor-bakery::") for node_id in ids)
    assert ["harbor-bakery::d-risk", "harbor-bakery::d-policy", "CAUSED"] in loaded["edges"]

    reloaded = FakeGraph()
    reloaded.nodes = json.loads(snap.read_text(encoding="utf-8"))["nodes"]
    reloaded.edges = [tuple(edge) for edge in json.loads(snap.read_text(encoding="utf-8"))["edges"]]
    assert any(node["metadata"].get("application_id") == "harbor-bakery" for node in reloaded.nodes)


def test_schema_failure_does_not_replace_snapshot(tmp_path, monkeypatch):
    graph = FakeGraph()
    snap = tmp_path / "g.json"
    snap.write_text('{"nodes":[{"id":"keep"}],"edges":[]}', encoding="utf-8")

    def fake_apply_case(*args, **kwargs):
        graph.nodes = [{"id": "broken", "type": "Decision"}]
        return {"application_id": "harbor-bakery", "applicant_name": "H"}

    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", snap)
    monkeypatch.setattr("backend.import_service.apply_case", fake_apply_case)
    monkeypatch.setattr("backend.stores.persist_graph", lambda graph: {"skipped": True})
    monkeypatch.setattr(
        "backend.ontology.validate_graph",
        lambda graph, application_id=None: {
            "conforms": False,
            "violations": [{"message": "Decision.category missing"}],
            "checked": 1,
        },
    )

    try:
        import_application(
            graph,
            files=[{"filename": "a.txt", "content": b"x"}],
            applicant_name="Harbor Bakehouse Pvt Ltd",
            application_id="harbor-bakery",
        )
        raise AssertionError("schema failure should raise")
    except LendingImportError as exc:
        assert "schema" in str(exc)
    assert json.loads(snap.read_text(encoding="utf-8"))["nodes"][0]["id"] == "keep"


def test_write_graph_snapshot_leaves_old_file_when_save_fails(tmp_path):
    dest = tmp_path / "lending_graph.json"
    dest.write_text('{"ok":1}', encoding="utf-8")

    class Boom:
        def save_to_file(self, path):
            raise RuntimeError("disk")

        def to_dict(self):
            raise RuntimeError("disk")

    try:
        write_graph_snapshot(Boom(), dest)
        raise AssertionError("save failure should raise")
    except RuntimeError:
        pass
    assert dest.read_text(encoding="utf-8") == '{"ok":1}'
