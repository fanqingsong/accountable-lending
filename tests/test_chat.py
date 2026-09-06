"""Chat generation tests — retrieve first, LLM only writes the sentence."""

from backend.chat import answer, extractive_answer, format_context, generate_answer


class FakeGraph:
    def __init__(self, nodes, edges):
        self._nodes = nodes
        self._edges = edges

    def to_dict(self):
        return {"nodes": self._nodes, "edges": self._edges}


def _payload():
    return {
        "query": "Sunrise 为什么转人工",
        "chunks": [
            {
                "kind": "Document",
                "text": "Revenue concentration: Café Amara 38%. Policy 7.3.",
                "application_id": "sunrise-coffee",
            }
        ],
        "decisions": [
            {
                "id": "d-risk",
                "category": "risk_classification",
                "outcome": "high_risk",
                "reasoning": "38% revenue concentration",
            },
            {
                "id": "d-policy",
                "category": "policy_check",
                "outcome": "manual_review_required",
                "reasoning": "Policy 7.3",
            },
            {
                "id": "d-final",
                "category": "final_decision",
                "outcome": "referred_to_manual_review",
                "reasoning": "routed to the manual review queue",
            },
        ],
        "caused": [{"from": "d-risk", "to": "d-policy"}, {"from": "d-policy", "to": "d-final"}],
        "entities": [{"text": "38%", "type": "PERCENT"}],
    }


def test_format_context_includes_chain_and_evidence():
    context = format_context(_payload())
    assert "high_risk" in context
    assert "referred_to_manual_review" in context
    assert "38%" in context
    assert "CAUSED d-risk -> d-policy" in context


def test_format_context_truncates_long_document_bodies():
    payload = _payload()
    payload["chunks"] = [{"kind": "Document", "text": "Cedar Mill " + ("x" * 5000)}]
    context = format_context(payload)
    assert "high_risk" in context
    assert len(context) <= 2400


def test_extractive_answer_names_the_decision_chain():
    text = extractive_answer(_payload())
    assert "risk_classification=high_risk" in text
    assert "final_decision=referred_to_manual_review" in text
    assert "38%" in text


def test_generate_answer_uses_retrieve_context_not_free_invention():
    seen = {}

    def fake_complete(prompt, system):
        seen["prompt"] = prompt
        seen["system"] = system
        return "因为收入集中度 38% 触发 Policy 7.3，所以转人工审。"

    result = generate_answer("Sunrise 为什么转人工", _payload(), complete=fake_complete)
    assert result["source"] == "ollama"
    assert "38%" in seen["prompt"]
    assert "referred_to_manual_review" in seen["prompt"]
    assert "禁止编造" in seen["system"]
    assert result["answer"].startswith("因为收入集中度")


def test_generate_answer_falls_back_when_complete_missing():
    result = generate_answer("Sunrise 为什么转人工", _payload(), complete=None)
    assert result["source"] == "extractive"
    assert "generation_error" not in result
    assert "referred_to_manual_review" in result["answer"]


def test_generate_answer_records_empty_model_output():
    result = generate_answer("Sunrise 为什么转人工", _payload(), complete=lambda prompt, system: "")
    assert result["source"] == "extractive"
    assert result["generation_error"] == "empty model output"
    assert "referred_to_manual_review" in result["answer"]


def test_answer_retrieves_before_calling_llm():
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
                "content": "Loan outcome",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                    "reasoning": "routed to the manual review queue",
                },
            },
        ],
        [{"source": "sunrise-coffee::application", "target": "d-final", "type": "HAS_DECISION"}],
    )
    seen = {}

    def fake_complete(prompt, system):
        seen["prompt"] = prompt
        return "已转人工。"

    result = answer(graph, "Sunrise 为什么转人工", complete=fake_complete)
    assert "referred_to_manual_review" in seen["prompt"]
    assert result["source"] == "ollama"
    assert result["answer"] == "已转人工。"
    assert result["decisions"][0]["outcome"] == "referred_to_manual_review"


def test_generate_answer_does_not_call_llm_without_retrieve_evidence():
    called = []

    def fake_complete(prompt, system):
        called.append(prompt)
        return "幻觉"

    result = generate_answer(
        "为什么转人工",
        {"decisions": [], "chunks": [], "caused": [], "entities": []},
        complete=fake_complete,
    )
    assert called == []
    assert result["source"] == "extractive"
    assert result["answer"] == "图谱里没有找到相关证据。"


def test_answer_empty_query_does_not_invent():
    result = answer(FakeGraph([], []), "   ", complete=lambda prompt, system: "幻觉")
    assert result["answer"] == "图谱里没有找到相关证据。"
    assert result["source"] == "extractive"
    assert "generation_error" not in result


def test_answer_falls_back_when_complete_times_out():
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
                "content": "Loan outcome",
                "metadata": {
                    "application_id": "sunrise-coffee",
                    "category": "final_decision",
                    "outcome": "referred_to_manual_review",
                    "reasoning": "routed to the manual review queue",
                },
            },
        ],
        [{"source": "sunrise-coffee::application", "target": "d-final", "type": "HAS_DECISION"}],
    )

    def boom(prompt, system):
        raise TimeoutError("timed out")

    result = answer(graph, "Sunrise 为什么转人工", complete=boom)
    assert result["source"] == "extractive"
    assert result["generation_error"] == "timed out"
    assert "referred_to_manual_review" in result["answer"]
