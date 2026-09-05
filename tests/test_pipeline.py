"""Unit tests for case scoping and application attachment."""

from app.pipeline import (
    apply_payload,
    attach_case,
    ensure_seed_application,
    list_applications,
    reason_subject,
    scope_build_result,
    scope_id,
    slugify,
)


def test_slugify_and_reason_subject():
    assert slugify("Harbor Bakehouse Pvt Ltd") == "harbor-bakehouse-pvt-ltd"
    assert reason_subject("Harbor Bakehouse Pvt Ltd") == "HarborBakehousePvtLtd"
    assert slugify("!!!") == "application"


def test_scope_id_is_idempotent():
    assert scope_id("harbor", "Priya") == "harbor::Priya"
    assert scope_id("harbor", "harbor::Priya") == "harbor::Priya"


def test_scope_build_result_prefixes_endpoints_and_stamps_application_id():
    scoped = scope_build_result(
        {
            "entities": [{"id": "A", "text": "Harbor", "type": "ORG"}],
            "relationships": [{"source": "A", "target": "A", "type": "related_to"}],
        },
        "harbor",
    )
    assert scoped["entities"][0]["id"] == "harbor::A"
    assert scoped["entities"][0]["metadata"]["application_id"] == "harbor"
    assert scoped["relationships"][0]["source"] == "harbor::A"
    assert scoped["relationships"][0]["target"] == "harbor::A"


class FakeGraph:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node_id, node_type, content=None, **kwargs):
        self.nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "content": content,
                "metadata": kwargs,
            }
        )

    def add_edge(self, source, target, edge_type, weight=1.0, **kwargs):
        self.edges.append((source, target, edge_type))

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": [
                {"source": source, "target": target, "type": edge_type}
                for source, target, edge_type in self.edges
            ],
        }


def test_apply_payload_adds_application_document_and_contains():
    graph = FakeGraph()
    payload = {
        "nodes": [{"id": "h::A", "type": "ORG", "content": "Harbor", "metadata": {}}],
        "edges": [],
    }
    member_ids = apply_payload(
        graph,
        payload,
        "h",
        "Harbor Bakehouse",
        [{"name": "profile.txt", "text": "x"}],
    )
    assert member_ids == ["h::A"]
    types = {node["type"] for node in graph.nodes}
    assert {"ORG", "Application", "Document"} <= types
    assert ("h::application", "h::doc::profile.txt", "HAS_DOCUMENT") in graph.edges
    assert ("h::application", "h::A", "CONTAINS") in graph.edges


def test_ensure_seed_application_is_idempotent():
    graph = FakeGraph()
    graph.add_node("maya", "PERSON", content="Maya")
    ensure_seed_application(graph)
    ensure_seed_application(graph)
    apps = [node for node in graph.nodes if node["type"] == "Application"]
    assert len(apps) == 1
    assert list_applications(graph)[0]["application_id"] == "sunrise-coffee"


def test_attach_case_does_not_contain_itself():
    graph = FakeGraph()
    attach_case(graph, "h", "Harbor", [], ["h::application", "h::A"])
    assert ("h::application", "h::application", "CONTAINS") not in graph.edges
    assert ("h::application", "h::A", "CONTAINS") in graph.edges


def test_attach_case_stamps_document_body():
    graph = FakeGraph()
    attach_case(
        graph,
        "h",
        "Harbor",
        [{"name": "risk_notes.txt", "text": "Café Amara 38%."}],
        [],
    )
    docs = [node for node in graph.nodes if node["type"] == "Document"]
    assert docs[0]["metadata"]["body"] == "Café Amara 38%."
