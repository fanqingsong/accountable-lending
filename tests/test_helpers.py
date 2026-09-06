"""Tests for demo package helper functions.

These are fast and deterministic; they never import semantica (the demo
package only imports semantica inside its stage functions).
"""

import copy

import demo


# ---------------------------------------------------------------------------
# _iri_for
# ---------------------------------------------------------------------------


def test_iri_for_plain_text_becomes_slug():
    assert (
        demo._iri_for("Sunrise Coffee Roasters")
        == "https://example.org/lending#Sunrise-Coffee-Roasters"
    )


def test_iri_for_handles_punctuation_and_whitespace():
    assert demo._iri_for("Kochi, Kerala") == "https://example.org/lending#Kochi-Kerala"
    assert demo._iri_for("  padded  ") == "https://example.org/lending#padded"


def test_iri_for_handles_unicode():
    # NFKD normalization strips diacritics; combining marks are non-word chars.
    assert demo._iri_for("Café Amara") == "https://example.org/lending#Cafe-Amara"


def test_iri_for_collapses_repeated_dashes():
    assert demo._iri_for("a--b  c") == "https://example.org/lending#a-b-c"


def test_iri_for_empty_after_strip_becomes_unnamed():
    for value in ("", "   ", "!!!", "--"):
        assert demo._iri_for(value) == "https://example.org/lending#unnamed"


def test_iri_for_non_string_input_and_determinism():
    first = demo._iri_for(123)
    second = demo._iri_for(123)
    assert first == "https://example.org/lending#123"
    assert first == second


# ---------------------------------------------------------------------------
# _with_iris
# ---------------------------------------------------------------------------


def test_with_iris_rewrites_entity_ids_and_relationship_endpoints():
    kg = {
        "entities": [
            {"id": "Sunrise Coffee Roasters", "type": "Business"},
            {"id": "Kochi, Kerala", "type": "Location"},
        ],
        "relationships": [
            {
                "source_id": "Sunrise Coffee Roasters",
                "target_id": "Kochi, Kerala",
                "type": "located_in",
            }
        ],
    }

    out = demo._with_iris(kg)

    for entity in out["entities"]:
        assert entity["id"].startswith("https://example.org/lending#")
    rel = out["relationships"][0]
    assert rel["source_id"] == "https://example.org/lending#Sunrise-Coffee-Roasters"
    assert rel["target_id"] == "https://example.org/lending#Kochi-Kerala"


def test_with_iris_leaves_unmatched_endpoints_unchanged():
    kg = {
        "entities": [{"id": "A", "type": "Business"}],
        "relationships": [{"source_id": "A", "target_id": "Ghost Endpoint", "type": "relates_to"}],
    }

    out = demo._with_iris(kg)

    rel = out["relationships"][0]
    assert rel["source_id"] == "https://example.org/lending#A"
    assert rel["target_id"] == "Ghost Endpoint"


def test_with_iris_falls_back_to_source_target_keys():
    kg = {
        "entities": [{"id": "A", "type": "Business"}],
        "relationships": [{"source": "A", "target": "A", "type": "self"}],
    }

    out = demo._with_iris(kg)

    rel = out["relationships"][0]
    assert rel["source_id"] == "https://example.org/lending#A"
    assert rel["target_id"] == "https://example.org/lending#A"


def test_with_iris_does_not_mutate_input():
    kg = {
        "entities": [{"id": "Kochi, Kerala", "type": "Location"}],
        "relationships": [
            {"source_id": "Kochi, Kerala", "target_id": "Kochi, Kerala", "type": "self"}
        ],
    }
    snapshot = copy.deepcopy(kg)

    demo._with_iris(kg)

    assert kg == snapshot


def test_with_iris_is_deterministic():
    kg = {
        "entities": [{"id": "Kochi, Kerala", "type": "Location"}],
        "relationships": [],
    }
    assert demo._with_iris(kg) == demo._with_iris(kg)
