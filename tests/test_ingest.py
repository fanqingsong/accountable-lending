"""Ingest / extract live in prefect/lending_prefect, not backend.application."""

from lending_prefect.ingest import scope_build_result, scope_id, to_nodes_edges


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


def test_application_does_not_own_ingest():
    from pathlib import Path

    package = Path(__file__).resolve().parent.parent / "backend" / "application"
    text = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    assert "def ingest_files" not in text
    assert "def extract(" not in text
    assert "FileIngestor" not in text
    assert "GraphBuilder" not in text
