"""Schema validation and Neo4j constraint helpers."""

from backend.ontology import (
    OWL_TTL,
    SHACL_TTL,
    apply_schema_constraints,
    neo4j_constraints,
    render_owl,
    render_shacl,
    required_fields,
    required_relationships,
    validate_graph,
)


class FakeGraph:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def to_dict(self):
        return {"nodes": self._nodes, "edges": self._edges}


def _valid_sunrise():
    return FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "properties": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "d-final",
                "type": "decision",
                "properties": {"category": "final_decision", "outcome": "referred_to_manual_review"},
            },
        ],
        [{"source": "sunrise-coffee::application", "target": "d-final", "type": "HAS_DECISION"}],
    )


def test_required_shape_comes_from_json():
    assert required_fields()["Application"] == ["application_id"]
    assert required_fields()["Decision"] == ["category", "outcome"]
    assert required_fields()["decision"] == ["category", "outcome"]
    names = [item["name"] for item in required_relationships()]
    assert names == ["HAS_DECISION"]


def test_projections_match_checked_in_turtle():
    assert OWL_TTL.read_text(encoding="utf-8") == render_owl()
    assert SHACL_TTL.read_text(encoding="utf-8") == render_shacl()


def test_neo4j_property_constraints_follow_required_fields():
    names = [name for name, _cypher in neo4j_constraints()]
    assert names == [
        "lending_entity_id",
        "application_id",
        "decision_category",
        "decision_outcome",
    ]


def test_validate_graph_accepts_complete_case():
    report = validate_graph(_valid_sunrise())
    assert report["conforms"] is True
    assert report["violations"] == []


def test_validate_graph_rejects_decision_without_outcome():
    graph = FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {"id": "d-bad", "type": "decision", "metadata": {"category": "final_decision"}},
        ],
        [{"source": "sunrise-coffee::application", "target": "d-bad", "type": "HAS_DECISION"}],
    )
    report = validate_graph(graph, application_id="sunrise-coffee")
    assert report["conforms"] is False
    assert any(item["field"] == "outcome" for item in report["violations"])


def test_validate_graph_rejects_application_without_decision():
    graph = FakeGraph(
        [{"id": "harbor-bakery::application", "type": "Application", "metadata": {"application_id": "harbor-bakery"}}],
        [],
    )
    report = validate_graph(graph)
    assert report["conforms"] is False
    assert any(item["field"] == "HAS_DECISION" for item in report["violations"])


def test_apply_schema_constraints_records_applied_and_skipped():
    class Store:
        def execute_query(self, query, parameters=None):
            if "IS NOT NULL" in query:
                raise RuntimeError("Enterprise only")
            return {"success": True}

    result = apply_schema_constraints(Store())
    assert "lending_entity_id" in result["applied"]
    assert any(item["name"] == "decision_category" for item in result["skipped"])
