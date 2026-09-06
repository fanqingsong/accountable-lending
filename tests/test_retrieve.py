"""GraphRAG retrieve tests — keyword + graph expansion, no Qdrant required."""

from backend.retrieve import expand_query, hinted_applications, retrieve, score_text


class FakeGraph:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def to_dict(self):
        return {"nodes": self._nodes, "edges": self._edges}


def _sunrise_graph():
    return FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "content": "Sunrise Coffee Roasters LLC",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "sunrise-coffee::doc::risk_notes.txt",
                "type": "Document",
                "content": "risk_notes.txt",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "body": "Revenue concentration: Café Amara 38%. Thin credit history.",
                },
            },
            {
                "id": "sunrise-coffee::38%",
                "type": "PERCENT",
                "content": "38%",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "d-risk",
                "type": "decision",
                "content": "Loan application for Sunrise Coffee Roasters LLC",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "risk_classification",
                    "outcome": "high_risk",
                    "reasoning": "38% revenue concentration",
                },
            },
            {
                "id": "d-policy",
                "type": "decision",
                "content": "Internal lending policy",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "policy_check",
                    "outcome": "manual_review_required",
                },
            },
            {
                "id": "d-final",
                "type": "decision",
                "content": "Loan outcome for Sunrise Coffee Roasters LLC",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                    "reasoning": "routed to the manual review queue",
                },
            },
        ],
        [
            {"source": "d-risk", "target": "d-policy", "type": "CAUSED"},
            {"source": "d-policy", "target": "d-final", "type": "CAUSED"},
        ],
    )


def test_expand_query_adds_manual_review_for_chinese():
    expanded = expand_query("Sunrise 为什么转人工")
    assert "manual review" in expanded
    assert "38%" in expanded


def test_retrieve_manual_review_returns_notes_entities_and_caused_chain():
    payload = retrieve(_sunrise_graph(), "为什么转人工")

    chunk_text = " ".join(hit["text"] for hit in payload["chunks"])
    assert "38%" in chunk_text or "Thin credit" in chunk_text

    outcomes = {item["outcome"] for item in payload["decisions"]}
    assert "high_risk" in outcomes
    assert "manual_review_required" in outcomes
    assert "referred_to_manual_review" in outcomes

    caused = {(link["from"], link["to"]) for link in payload["caused"]}
    assert ("d-risk", "d-policy") in caused
    assert ("d-policy", "d-final") in caused

    entity_texts = {item["text"] for item in payload["entities"]}
    assert "38%" in entity_texts


def test_retrieve_uses_has_decision_when_decisions_lack_application_id():
    graph = FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "content": "Sunrise Coffee Roasters LLC",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "d-final",
                "type": "decision",
                "content": "Loan outcome for Sunrise Coffee Roasters LLC",
                "metadata": {
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                },
            },
            {
                "id": "d-risk",
                "type": "decision",
                "content": "Loan application for Sunrise Coffee Roasters LLC",
                "metadata": {"category": "risk_classification", "outcome": "high_risk"},
            },
        ],
        [
            {"source": "sunrise-coffee::application", "target": "d-final", "type": "HAS_DECISION"},
            {"source": "sunrise-coffee::application", "target": "d-risk", "type": "HAS_DECISION"},
            {"source": "d-risk", "target": "d-final", "type": "CAUSED"},
        ],
    )
    payload = retrieve(graph, "Sunrise 为什么转人工")
    outcomes = {item["outcome"] for item in payload["decisions"]}
    assert "referred_to_manual_review" in outcomes
    assert "high_risk" in outcomes
    assert any(link["from"] == "d-risk" and link["to"] == "d-final" for link in payload["caused"])


def test_retrieve_reads_contextgraph_properties_shape():
    graph = FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "properties": {"application_id": "sunrise-coffee", "content": "Sunrise Coffee Roasters LLC"},
            },
            {
                "id": "d-final",
                "type": "decision",
                "properties": {
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                    "content": "Loan outcome for Sunrise Coffee Roasters LLC",
                    "reasoning": "routed to the manual review queue",
                },
            },
        ],
        [{"source_id": "sunrise-coffee::application", "target_id": "d-final", "type": "HAS_DECISION"}],
    )
    payload = retrieve(graph, "Sunrise 为什么转人工")
    assert payload["decisions"][0]["outcome"] == "referred_to_manual_review"


def test_hinted_applications_reads_graph_not_baked_in_case_ids():
    graph = FakeGraph(
        [
            {
                "id": "oak-mill::application",
                "type": "Application",
                "content": "Oak Mill Roastery",
                "metadata": {"application_id": "oak-mill"},
            }
        ],
        [],
    )
    assert hinted_applications(graph, "Oak Mill 为什么转人工") == ["oak-mill"]
    assert hinted_applications(graph, "为什么转人工") == []


def test_retrieve_scopes_to_named_application_from_graph():
    graph = FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "content": "Sunrise Coffee Roasters LLC",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "oak-mill::application",
                "type": "Application",
                "content": "Oak Mill Roastery",
                "metadata": {"application_id": "oak-mill"},
            },
            {
                "id": "d-sunrise",
                "type": "decision",
                "content": "Loan outcome for Sunrise",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                },
            },
            {
                "id": "d-oak",
                "type": "decision",
                "content": "Loan outcome for Oak Mill",
                "metadata": {
                    "application_id": "oak-mill",
                    "category": "final_decision",
                    "outcome": "approved",
                },
            },
        ],
        [
            {"source": "sunrise-coffee::application", "target": "d-sunrise", "type": "HAS_DECISION"},
            {"source": "oak-mill::application", "target": "d-oak", "type": "HAS_DECISION"},
        ],
    )
    payload = retrieve(graph, "Oak Mill 为什么转人工")
    outcomes = {item["outcome"] for item in payload["decisions"]}
    assert outcomes == {"approved"}


def test_retrieve_ignores_lowercase_caused():
    graph = FakeGraph(
        [
            {
                "id": "sunrise-coffee::application",
                "type": "Application",
                "content": "Sunrise Coffee Roasters LLC",
                "metadata": {"application_id": "sunrise-coffee"},
            },
            {
                "id": "d-risk",
                "type": "decision",
                "content": "Loan application",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "risk_classification",
                    "outcome": "high_risk",
                },
            },
            {
                "id": "d-final",
                "type": "decision",
                "content": "Loan outcome",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                },
            },
        ],
        [{"source": "d-risk", "target": "d-final", "type": "caused"}],
    )
    payload = retrieve(graph, "Sunrise 为什么转人工")
    assert payload["caused"] == []


def test_retrieve_empty_query_is_empty():
    assert retrieve(_sunrise_graph(), "   ")["chunks"] == []


def test_score_text_counts_term_hits():
    assert score_text("manual review required", ["manual", "review"]) == 2
