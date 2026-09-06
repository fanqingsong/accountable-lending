"""Unit tests for case scoping and application attachment."""

from pathlib import Path

from backend.application import (
    HIGH_RISK_FLAG,
    REQUIRES_MANUAL_REVIEW,
    THIN_CREDIT_HISTORY,
    attach_case,
    attach_decision_chain,
    ensure_seed_application,
    list_applications,
    load_policy_facts,
    policy_facts_from_graph,
    reason_subject,
    slugify,
)
from lending_prefect.attach import apply_payload
from lending_prefect.decide import record_decision_chain


def test_slugify_and_reason_subject():
    assert slugify("Harbor Bakehouse Pvt Ltd") == "harbor-bakehouse-pvt-ltd"
    assert reason_subject("Harbor Bakehouse Pvt Ltd") == "HarborBakehousePvtLtd"
    assert slugify("!!!") == "application"


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


def test_load_policy_facts_reads_sidecar(tmp_path):
    notes = tmp_path / "risk_notes.txt"
    notes.write_text("notes", encoding="utf-8")
    (tmp_path / "policy_facts.json").write_text(
        '{"HighRiskFlag": true, "ThinCreditHistory": false}',
        encoding="utf-8",
    )
    assert load_policy_facts([notes]) == {
        HIGH_RISK_FLAG: True,
        THIN_CREDIT_HISTORY: False,
    }


def test_record_decision_chain_writes_requires_manual_review():
    graph = FakeDecideGraph()
    record_decision_chain(graph, "sunrise-coffee", "Sunrise Coffee Roasters LLC")
    assert policy_facts_from_graph(graph, "sunrise-coffee")[REQUIRES_MANUAL_REVIEW] is True


def test_record_decision_chain_clears_requires_manual_review_when_thin_credit_absent():
    graph = FakeDecideGraph(
        application_id="cedar-mill",
        **{
            HIGH_RISK_FLAG: True,
            THIN_CREDIT_HISTORY: False,
            REQUIRES_MANUAL_REVIEW: True,
        },
    )
    record_decision_chain(graph, "cedar-mill", "Cedar Mill Furniture Pvt Ltd")
    facts = policy_facts_from_graph(graph, "cedar-mill")
    assert facts[HIGH_RISK_FLAG] is True
    assert facts[REQUIRES_MANUAL_REVIEW] is False


class FakeDecideGraph:
    def __init__(self, application_id="sunrise-coffee", **facts):
        self.decision_calls = []
        self.edges = []
        self.nodes = [{"id": f"entity-{i}", "type": "ORG"} for i in range(8)]
        self.nodes.append(
            {
                "id": f"{application_id}::application",
                "type": "Application",
                "content": "Sunrise Coffee Roasters LLC",
                "metadata": {
                    "application_id": application_id,
                    HIGH_RISK_FLAG: True,
                    THIN_CREDIT_HISTORY: True,
                    REQUIRES_MANUAL_REVIEW: True,
                    **facts,
                },
            }
        )

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
    graph = FakeDecideGraph(
        application_id="harbor",
        **{
            HIGH_RISK_FLAG: False,
            THIN_CREDIT_HISTORY: False,
            REQUIRES_MANUAL_REVIEW: False,
        },
    )
    decisions = record_decision_chain(
        graph,
        "harbor",
        "Harbor Bakehouse Pvt Ltd",
        entity_ids=["harbor::Priya"],
    )

    assert graph.decision_calls[0]["entities"] == ["harbor::Priya"]
    assert "Harbor Bakehouse Pvt Ltd" in graph.decision_calls[0]["scenario"]
    assert [call["outcome"] for call in graph.decision_calls] == [
        "standard_risk",
        "policy_cleared",
        "approved",
    ]
    assert set(decisions) == {"risk_classification", "policy_check", "final_decision"}


def test_record_decision_chain_follows_cedar_mill_facts():
    graph = FakeDecideGraph(
        application_id="cedar-mill",
        **{
            HIGH_RISK_FLAG: True,
            THIN_CREDIT_HISTORY: False,
            REQUIRES_MANUAL_REVIEW: False,
        },
    )
    record_decision_chain(graph, "cedar-mill", "Cedar Mill Furniture Pvt Ltd")
    assert [call["outcome"] for call in graph.decision_calls] == [
        "high_risk",
        "policy_cleared",
        "approved",
    ]


def test_cedar_mill_sidecar_declares_high_risk_without_thin_credit():
    pack = Path(__file__).resolve().parent.parent / "data" / "samples" / "cedar-mill"
    facts = load_policy_facts(sorted(pack.glob("*.txt")))
    assert facts == {HIGH_RISK_FLAG: True, THIN_CREDIT_HISTORY: False}


def test_application_module_does_not_import_prefect():
    package = Path(__file__).resolve().parent.parent / "backend" / "application"
    for path in package.glob("*.py"):
        assert "prefect" not in path.read_text(encoding="utf-8").lower(), path


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
