"""application_flow composes Application leaves without returning a ContextGraph."""

import json
from pathlib import Path

from lending_prefect.flows import application_flow, read_application_job, submit_application_run
from lending_prefect.attach import apply_payload
from lending_prefect.snapshot import write_graph_snapshot


class FakeGraph:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node_id, node_type, content=None, **kwargs):
        self.nodes.append(
            {"id": node_id, "type": node_type, "content": content, "metadata": kwargs}
        )

    def add_edge(self, source, target, edge_type, weight=1.0, **kwargs):
        self.edges.append((source, target, edge_type))

    def to_dict(self):
        return {"nodes": self.nodes, "edges": list(self.edges)}

    def load_from_file(self, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.nodes = payload.get("nodes") or []
        self.edges = [tuple(edge) for edge in payload.get("edges") or []]

    def save_to_file(self, path):
        Path(path).write_text(json.dumps(self.to_dict()), encoding="utf-8")


def test_application_flow_task_order_and_serializable_result(tmp_path, monkeypatch):
    order = []
    graph = FakeGraph()

    monkeypatch.setattr(
        "lending_prefect.flows.ingest_files",
        lambda paths: order.append("ingest") or [{"name": "a.txt", "text": "hello"}],
    )
    monkeypatch.setattr(
        "lending_prefect.flows.documents_to_payload",
        lambda documents, application_id: order.append("extract")
        or {
            "nodes": [{"id": f"{application_id}::A", "type": "ORG", "content": "A", "metadata": {}}],
            "edges": [],
        },
    )

    def fake_apply(graph, payload, application_id, applicant_name, documents, policy_facts=None):
        order.append("attach")
        return apply_payload(graph, payload, application_id, applicant_name, documents, policy_facts)

    def fake_decide(graph, application_id, applicant, entity_ids=None):
        order.append("decide")
        return {
            "risk_classification": f"{application_id}::d-risk",
            "policy_check": f"{application_id}::d-policy",
            "final_decision": f"{application_id}::d-final",
        }

    monkeypatch.setattr("lending_prefect.flows.apply_payload", fake_apply)
    monkeypatch.setattr("lending_prefect.flows.record_decision_chain", fake_decide)
    monkeypatch.setattr("lending_prefect.flows.load_graph", lambda path=None: graph)
    monkeypatch.setattr(
        "lending_prefect.flows.write_graph_snapshot",
        lambda g, path=None: order.append("snap") or write_graph_snapshot(g, path),
    )
    monkeypatch.setattr(
        "backend.ontology.validate_graph",
        lambda graph, application_id=None: order.append("validate")
        or {"conforms": True, "violations": [], "checked": 1},
    )
    monkeypatch.setattr(
        "backend.stores.persist_graph",
        lambda g: order.append("persist") or {"skipped": True},
    )

    snap = tmp_path / "lending_graph.json"
    result = application_flow(
        application_id="harbor-bakery",
        applicant_name="Harbor Bakehouse Pvt Ltd",
        paths=[str(tmp_path / "a.txt")],
        policy_facts={"HighRiskFlag": True, "ThinCreditHistory": True},
        snapshot_path=str(snap),
        index_vectors=False,
    )
    staged = [name for name in order if name in {"ingest", "extract", "attach", "decide", "validate", "persist"}]
    assert staged == ["ingest", "extract", "attach", "decide", "validate", "persist"]
    assert result["application_id"] == "harbor-bakery"
    assert "graph" not in result
    assert not any(key == "graph" for key in result)
    assert snap.is_file()
    loaded = json.loads(snap.read_text(encoding="utf-8"))
    assert any(node.get("id") == "harbor-bakery::application" for node in loaded["nodes"])


def test_validate_failure_does_not_replace_snapshot(tmp_path, monkeypatch):
    snap = tmp_path / "g.json"
    snap.write_text('{"nodes":[{"id":"keep"}],"edges":[]}', encoding="utf-8")
    graph = FakeGraph()
    graph.nodes = [{"id": "broken", "type": "Decision"}]

    monkeypatch.setattr(
        "lending_prefect.flows.ingest_files",
        lambda paths: [{"name": "a.txt", "text": "x"}],
    )
    monkeypatch.setattr(
        "lending_prefect.flows.documents_to_payload",
        lambda documents, application_id: {"nodes": [], "edges": []},
    )
    monkeypatch.setattr("lending_prefect.flows.apply_payload", lambda *a, **k: ["e1"])
    monkeypatch.setattr(
        "lending_prefect.flows.record_decision_chain",
        lambda *a, **k: {"final_decision": "d1"},
    )
    monkeypatch.setattr("lending_prefect.flows.load_graph", lambda path=None: graph)
    monkeypatch.setattr("backend.ontology.validate_graph", lambda *a, **k: {
        "conforms": False,
        "violations": [{"message": "Decision.category missing"}],
        "checked": 1,
    })
    monkeypatch.setattr(
        "backend.stores.persist_graph",
        lambda g: (_ for _ in ()).throw(AssertionError("must not persist")),
    )

    try:
        application_flow(
            application_id="harbor-bakery",
            applicant_name="Harbor",
            paths=[str(tmp_path / "a.txt")],
            snapshot_path=str(snap),
            index_vectors=False,
        )
        raise AssertionError("schema failure should raise")
    except ValueError as exc:
        assert "schema" in str(exc)
    assert json.loads(snap.read_text(encoding="utf-8"))["nodes"][0]["id"] == "keep"


def test_submit_in_process_is_readable(tmp_path, monkeypatch):
    monkeypatch.delenv("PREFECT_API_URL", raising=False)
    monkeypatch.setattr(
        "lending_prefect.flows.application_flow",
        lambda **kwargs: {
            "application_id": kwargs["application_id"],
            "applicant_name": kwargs["applicant_name"],
            "decisions": {"final_decision": "d1"},
            "entity_count": 1,
        },
    )
    body = submit_application_run(
        application_id="harbor-bakery",
        applicant_name="Harbor",
        paths=[str(tmp_path / "a.txt")],
        snapshot_path=str(tmp_path / "g.json"),
        index_vectors=False,
    )
    assert body["status"] == "COMPLETED"
    assert body["flow_run_id"]
    loaded = read_application_job(body["flow_run_id"])
    assert loaded["application_id"] == "harbor-bakery"
    assert loaded["decisions"]["final_decision"] == "d1"
