"""Unit tests for case scoping and application attachment."""

from backend.pipeline import (
    apply_payload,
    attach_case,
    attach_decision_chain,
    ensure_seed_application,
    list_applications,
    reason,
    reason_subject,
    record_decision_chain,
    scope_build_result,
    scope_id,
    slugify,
    to_nodes_edges,
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


def test_attach_decision_chain_adds_has_decision():
    graph = FakeGraph()
    attach_case(graph, "h", "Harbor", [], [])
    attach_decision_chain(
        graph,
        "h",
        {"risk_classification": "d-risk", "final_decision": "d-final"},
    )
    assert ("h::application", "d-risk", "HAS_DECISION") in graph.edges
    assert ("h::application", "d-final", "HAS_DECISION") in graph.edges


def test_list_applications_reads_properties_shape():
    graph = FakeGraph()
    graph.nodes.append(
        {
            "id": "oak-mill::application",
            "type": "Application",
            "properties": {"application_id": "oak-mill", "content": "Oak Mill"},
        }
    )
    listed = list_applications(graph)
    assert listed[0]["application_id"] == "oak-mill"
    assert listed[0]["name"] == "Oak Mill"


def test_to_nodes_edges_translates_vocabulary():
    build_result = {
        "entities": [
            {
                "id": "ent-1",
                "type": "Business",
                "text": "Sunrise Coffee Roasters",
                "confidence": 0.95,
            },
            {"id": "ent-2", "type": "Location", "text": "Kochi"},
        ],
        "relationships": [
            {"source": "ent-1", "target": "ent-2", "type": "located_in", "weight": 0.8},
            {"source": "ent-2", "target": "ent-1", "type": "relates_to"},
        ],
    }

    out = to_nodes_edges(build_result)

    assert out["nodes"][0] == {
        "id": "ent-1",
        "type": "Business",
        "content": "Sunrise Coffee Roasters",
        "metadata": {"confidence": 0.95},
    }
    assert out["nodes"][1]["metadata"] == {"confidence": 1.0}
    assert out["edges"][0] == {
        "source": "ent-1",
        "target": "ent-2",
        "type": "located_in",
        "weight": 0.8,
    }
    assert out["edges"][1]["weight"] == 1.0


def test_to_nodes_edges_empty_input():
    assert to_nodes_edges({}) == {"nodes": [], "edges": []}


def test_reason_derives_manual_review():
    conclusions = reason(object(), subject="SunriseCoffeeRoasters")
    assert "RequiresManualReview(SunriseCoffeeRoasters)" in conclusions


class FakeDecideGraph:
    def __init__(self):
        self.decision_calls = []
        self.edges = []
        self.nodes = [{"id": f"entity-{i}", "type": "ORG"} for i in range(8)]

    def to_dict(self):
        return {"nodes": self.nodes}

    def record_decision(self, **kwargs):
        self.decision_calls.append(kwargs)
        return f"decision-{len(self.decision_calls)}"

    def add_edge(self, source, target, edge_type, **kwargs):
        self.edges.append((source, target, edge_type))


def test_record_decision_chain_records_caused_and_has_decision():
    graph = FakeDecideGraph()
    decisions = record_decision_chain(graph, "sunrise-coffee", "Sunrise Coffee Roasters LLC")

    assert len(graph.decision_calls) == 3
    assert [call["category"] for call in graph.decision_calls] == [
        "risk_classification",
        "policy_check",
        "final_decision",
    ]
    assert set(decisions) == {"risk_classification", "policy_check", "final_decision"}
    caused = [edge for edge in graph.edges if edge[2] == "CAUSED"]
    assert caused == [
        (decisions["risk_classification"], decisions["policy_check"], "CAUSED"),
        (decisions["policy_check"], decisions["final_decision"], "CAUSED"),
    ]
    assert ("sunrise-coffee::application", decisions["risk_classification"], "HAS_DECISION") in graph.edges
    assert ("sunrise-coffee::application", decisions["final_decision"], "HAS_DECISION") in graph.edges


def test_record_decision_chain_uses_applicant_entity_ids_and_approval_path():
    graph = FakeDecideGraph()
    decisions = record_decision_chain(
        graph,
        "harbor",
        "Harbor Bakehouse Pvt Ltd",
        entity_ids=["harbor::Priya"],
        high_risk=False,
        thin_credit=False,
    )

    assert graph.decision_calls[0]["entities"] == ["harbor::Priya"]
    assert "Harbor Bakehouse Pvt Ltd" in graph.decision_calls[0]["scenario"]
    assert [call["outcome"] for call in graph.decision_calls] == [
        "standard_risk",
        "policy_cleared",
        "approved",
    ]
    assert set(decisions) == {"risk_classification", "policy_check", "final_decision"}


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
