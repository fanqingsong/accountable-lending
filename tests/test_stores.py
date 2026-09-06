"""Unit tests for Neo4j persist helpers. No running database required."""

from backend.stores import (
    _graph_payload,
    _node_props,
    _safe_label,
    _safe_rel,
    connect_store,
    persist_graph,
)


def test_safe_label_strips_and_prefixes_digits():
    assert _safe_label("ORG") == "ORG"
    assert _safe_label("decision") == "decision"
    assert _safe_label("Café Amara") == "Caf_Amara"
    assert _safe_label("123") == "T_123"
    assert _safe_label("") == "Entity"
    assert _safe_label("!!!") == "Entity"


def test_safe_rel_uppercases():
    assert _safe_rel("related_to") == "RELATED_TO"
    assert _safe_rel("CAUSED") == "CAUSED"
    assert _safe_rel("") == "RELATED_TO"


def test_node_props_flattens_metadata_and_properties():
    props = _node_props(
        {
            "id": "sunrise",
            "type": "ORG",
            "content": "Sunrise Coffee Roasters",
            "metadata": {"confidence": 0.9, "nested": {"x": 1}},
            "properties": {"application_id": "sunrise-coffee"},
        }
    )
    assert props["application_id"] == "sunrise-coffee"
    assert props["entity_id"] == "sunrise"
    assert props["text"] == "Sunrise Coffee Roasters"
    assert props["node_type"] == "ORG"
    assert props["confidence"] == 0.9
    assert props["nested"] == "{'x': 1}"


def test_graph_payload_reads_to_dict():
    class Graph:
        def to_dict(self):
            return {
                "nodes": [{"id": "a", "type": "ORG", "content": "A"}],
                "edges": [{"source": "a", "target": "a", "type": "CAUSED"}],
            }

    nodes, edges = _graph_payload(Graph())
    assert nodes[0]["id"] == "a"
    assert edges[0]["type"] == "CAUSED"


def test_connect_store_returns_none_without_uri(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert connect_store() is None


class FakeStore:
    def __init__(self):
        self.queries = []

    def execute_query(self, query, parameters=None):
        self.queries.append((query, parameters or {}))
        return {"success": True, "records": []}

    def close(self):
        self.closed = True


class FakePersistGraph:
    def to_dict(self):
        return {
            "nodes": [
                {"id": "risk-1", "type": "decision", "content": "high risk"},
                {"id": "final-1", "type": "decision", "content": "manual review"},
            ],
            "edges": [
                {"source": "risk-1", "target": "final-1", "type": "CAUSED", "weight": 1.0},
            ],
        }


def test_persist_graph_merges_nodes_and_caused_edges():
    store = FakeStore()
    result = persist_graph(FakePersistGraph(), store=store)

    assert result == {"nodes": 2, "edges": 1, "skipped": False}
    assert "CREATE CONSTRAINT" in store.queries[0][0]
    merge_nodes = [q for q, _ in store.queries if "MERGE (n:LendingNode" in q]
    assert len(merge_nodes) == 2
    caused = [q for q, p in store.queries if "CAUSED" in q]
    assert len(caused) == 1
    assert store.queries[-1][1]["src"] == "risk-1"
    assert store.queries[-1][1]["tgt"] == "final-1"


def test_persist_graph_skips_without_store_or_uri(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    result = persist_graph(FakePersistGraph())
    assert result["skipped"] is True
    assert result["nodes"] == 0


def test_persist_graph_does_not_close_caller_store():
    store = FakeStore()
    persist_graph(FakePersistGraph(), store=store)
    assert not hasattr(store, "closed")
