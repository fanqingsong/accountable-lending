"""Integration smoke test: runs the REAL semantica pipeline stages end to end.

Opt-in via `pytest -m integration` (the default run excludes it). It uses the
demo's real data files and the local spaCy model, so it is slower than the
unit tests but still well under a minute.
"""

import pytest

import demo


@pytest.mark.integration
def test_full_pipeline_smoke():
    # ingest -> extract -> graph -> reason -> decide
    documents = demo.stage_ingest()
    assert len(documents) == 3

    build_result = demo.stage_extract(documents)
    entities = build_result.get("entities", [])
    assert len(entities) >= 1

    graph = demo.stage_graph(build_result, documents)
    stats = graph.to_kg_dict().get("statistics", {})
    assert stats.get("entity_count", 0) >= 1
    payload = graph.to_dict()
    assert any(node.get("type") == "Application" for node in payload.get("nodes") or [])
    assert any(
        str(node.get("id") or "").startswith("sunrise-coffee::")
        for node in payload.get("nodes") or []
    )

    conclusions = demo.stage_reason(graph)
    assert conclusions, "expected at least one derived conclusion"

    decisions = demo.stage_decide(graph)
    assert set(decisions) == {"risk_classification", "policy_check", "final_decision"}
    payload = graph.to_dict()
    edges = payload.get("edges") or []
    assert any(edge.get("type") == "HAS_DECISION" for edge in edges)
    assert any(edge.get("type") == "CAUSED" for edge in edges)

    # the audit trail: upstream causal chain from the final decision
    chain = graph.get_causal_chain(
        decisions["final_decision"], direction="upstream", max_depth=5
    )
    assert len(chain) >= 2
