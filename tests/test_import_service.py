"""Tests for upload validation and duplicate application rejection."""

from app.import_service import LendingImportError, import_application, safe_filename
from app.pipeline import apply_payload


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
        return {"nodes": self.nodes, "edges": []}

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

    monkeypatch.setattr("app.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("app.import_service.GRAPH_JSON", tmp_path / "g.json")
    monkeypatch.setattr("app.stores.persist_graph", lambda graph: {"skipped": True})

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

    monkeypatch.setattr("app.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("app.import_service.GRAPH_JSON", tmp_path / "g.json")
    monkeypatch.setattr("app.import_service.apply_case", fake_apply_case)
    monkeypatch.setattr("app.stores.persist_graph", lambda graph: {"skipped": True})

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
    assert graph.saved.endswith("g.json")
