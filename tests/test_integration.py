"""Integration smoke test: runs the REAL semantica pipeline stages end to end.

Opt-in via `pytest -m integration` (the default run excludes it). It uses the
seed data files and the local spaCy model, so it is slower than the
unit tests but still well under a minute.
"""

from pathlib import Path

import pytest

from lending_prefect.flows import application_flow
from backend.application import DATA_DIR, load_graph


@pytest.mark.integration
def test_full_pipeline_smoke(tmp_path):
    snap = tmp_path / "lending_graph.json"
    result = application_flow(
        application_id="sunrise-coffee",
        applicant_name="Sunrise Coffee Roasters LLC",
        paths=[str(path) for path in sorted(DATA_DIR.glob("*.txt"))],
        snapshot_path=str(snap),
        index_vectors=False,
    )
    assert result["application_id"] == "sunrise-coffee"
    assert set(result["decisions"]) == {
        "risk_classification",
        "policy_check",
        "final_decision",
    }
    assert snap.is_file()

    graph = load_graph(snap)
    payload = graph.to_dict()
    assert any(node.get("type") == "Application" for node in payload.get("nodes") or [])
    assert any(
        str(node.get("id") or "").startswith("sunrise-coffee::")
        for node in payload.get("nodes") or []
    )
    edges = payload.get("edges") or []
    assert any(edge.get("type") == "HAS_DECISION" for edge in edges)
    assert any(edge.get("type") == "CAUSED" for edge in edges)

    chain = graph.get_causal_chain(
        result["decisions"]["final_decision"], direction="upstream", max_depth=5
    )
    assert len(chain) >= 2
