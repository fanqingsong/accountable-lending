"""Tests for upload validation and duplicate application rejection."""

from pathlib import Path

from backend.import_service import LendingImportError, import_application, safe_filename
from lending_prefect.attach import apply_payload
from lending_prefect.snapshot import write_graph_snapshot


def test_safe_filename_rejects_bad_types_and_paths():
    assert safe_filename("notes.txt") == "notes.txt"
    assert safe_filename("policy_facts.json") == "policy_facts.json"
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


def test_import_application_writes_files_and_submits_flow(tmp_path, monkeypatch):
    graph = FakeGraph()
    called = {}

    def fake_submit(**kwargs):
        called.update(kwargs)
        return {
            "application_id": kwargs["application_id"],
            "applicant_name": kwargs["applicant_name"],
            "flow_run_id": "local-1",
            "status": "COMPLETED",
            "entity_count": 2,
            "decisions": {"final_decision": "d1"},
        }

    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", tmp_path / "g.json")
    monkeypatch.setattr("backend.prefect_api.submit_application_run", fake_submit)

    result = import_application(
        graph,
        files=[{"filename": "a.txt", "content": b"hello"}],
        applicant_name="Harbor Bakehouse Pvt Ltd",
        high_risk=False,
        thin_credit=False,
    )
    assert result["application_id"] == "harbor-bakehouse-pvt-ltd"
    assert result["flow_run_id"] == "local-1"
    assert (tmp_path / "harbor-bakehouse-pvt-ltd" / "a.txt").read_bytes() == b"hello"
    assert called["policy_facts"] == {"HighRiskFlag": False, "ThinCreditHistory": False}
    assert called["paths"][0].endswith("a.txt")


def test_import_prefers_uploaded_policy_facts_json(tmp_path, monkeypatch):
    graph = FakeGraph()
    called = {}

    def fake_submit(**kwargs):
        called.update(kwargs)
        return {
            "application_id": kwargs["application_id"],
            "applicant_name": kwargs["applicant_name"],
            "flow_run_id": "local-2",
            "status": "COMPLETED",
        }

    monkeypatch.setattr("backend.import_service.UPLOADS", tmp_path)
    monkeypatch.setattr("backend.import_service.GRAPH_JSON", tmp_path / "g.json")
    monkeypatch.setattr("backend.prefect_api.submit_application_run", fake_submit)

    result = import_application(
        graph,
        files=[
            {"filename": "a.txt", "content": b"hello"},
            {
                "filename": "policy_facts.json",
                "content": b'{"HighRiskFlag": true, "ThinCreditHistory": false}',
            },
        ],
        applicant_name="Cedar Mill Furniture Pvt Ltd",
        application_id="cedar-mill",
        high_risk=True,
        thin_credit=True,
    )
    assert result["application_id"] == "cedar-mill"
    assert called["policy_facts"] == {"HighRiskFlag": True, "ThinCreditHistory": False}
    assert any(Path(path).name == "policy_facts.json" for path in called["paths"])


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
