"""Tests for the demo package's printable adapters, using lightweight fakes.

Decision / reason Implementation is tested through ``backend.pipeline``.
`stage_export` patches semantica's exporter / SHACL classes because they are
imported *inside* the function.
"""

from datetime import datetime, timezone
from pathlib import Path

import semantica.export
import semantica.ingest
import semantica.ontology
import semantica.ontology.ontology_validator
from semantica.context.decision_models import Decision

import demo


def test_stage_reason_prints_conclusions(capsys):
    conclusions = demo.stage_reason(object(), subject="SunriseCoffeeRoasters")

    assert "RequiresManualReview(SunriseCoffeeRoasters)" in conclusions
    out = capsys.readouterr().out
    assert "derived: RequiresManualReview(SunriseCoffeeRoasters)" in out


# ---------------------------------------------------------------------------
# stage_audit
# ---------------------------------------------------------------------------


class FakeAuditGraph:
    def __init__(self, chain, precedents):
        self.chain = chain
        self.precedents = precedents

    def get_causal_chain(self, decision_id, **kwargs):
        return self.chain

    def find_precedents(self, decision_id, limit=10, **kwargs):
        return self.precedents


def _make_decision(decision_id, category, outcome):
    return Decision(
        decision_id=decision_id,
        category=category,
        scenario="Loan application for Sunrise Coffee Roasters LLC",
        reasoning="Test reasoning",
        outcome=outcome,
        confidence=0.9,
        timestamp=datetime.now(timezone.utc),
        decision_maker="test_agent",
    )


def test_stage_audit_prints_causal_chain_and_no_precedents(capsys):
    chain = [
        _make_decision("decision-first", "risk_classification", "high_risk"),
        _make_decision("decision-final", "final_decision", "referred_to_manual_review"),
    ]
    graph = FakeAuditGraph(chain=chain, precedents=[])

    demo.stage_audit(graph, {"final_decision": "decision-final"})

    out = capsys.readouterr().out
    assert "decision-first" in out
    assert "decision-final" in out
    assert "risk_classification" in out
    assert "(none recorded" in out


# ---------------------------------------------------------------------------
# stage_ingest
# ---------------------------------------------------------------------------


class FakeFileObject:
    def __init__(self, text):
        self.text = text


class FakeIngestor:
    def __init__(self):
        self.ingested_paths = []

    def ingest_file(self, path, **options):
        self.ingested_paths.append(Path(path))
        return FakeFileObject(f"content of {Path(path).name}")


def test_stage_ingest_returns_three_documents_from_data_dir(monkeypatch, capsys):
    fake = FakeIngestor()
    monkeypatch.setattr(semantica.ingest, "FileIngestor", lambda: fake)

    documents = demo.stage_ingest()

    assert len(documents) == 3
    assert all(item["name"].endswith(".txt") and item["text"] for item in documents)

    # the DATA_DIR glob ("*.txt") is respected: exactly the three real files
    assert sorted(p.name for p in fake.ingested_paths) == [
        "business_profile.txt",
        "financials.txt",
        "risk_notes.txt",
    ]

    out = capsys.readouterr().out
    assert "ingested business_profile.txt" in out


# ---------------------------------------------------------------------------
# stage_export
# ---------------------------------------------------------------------------


class FakeExportGraph:
    def __init__(self):
        self.saved_paths = []

    def to_kg_dict(self):
        return {
            "entities": [
                {"id": "Sunrise Coffee Roasters", "type": "Business"},
                {"id": "Kochi, Kerala", "type": "Location"},
            ],
            "relationships": [
                {
                    "source_id": "Sunrise Coffee Roasters",
                    "target_id": "Kochi, Kerala",
                    "type": "located_in",
                },
                {
                    "source_id": "Kochi, Kerala",
                    "target_id": "Ghost Endpoint",
                    "type": "relates_to",
                },
            ],
        }

    def save_to_file(self, path):
        self.saved_paths.append(str(path))
        Path(path).write_text("{}", encoding="utf-8")


class FakeExporter:
    def __init__(self):
        self.exported = []

    def export_knowledge_graph(self, graph, file_path, format="turtle", **options):
        self.exported.append({"graph": graph, "file_path": str(file_path), "format": format})
        # demo counts triples by reading the file back; write a valid one
        Path(file_path).write_text(
            ":dummy a <https://example.org/lending#Decision> .\n", encoding="utf-8"
        )


class FakeSHACLGenerator:
    def __init__(self):
        self.generated = None

    def generate(self, ontology, **options):
        self.generated = ontology
        return {"shapes": True}

    def serialize(self, shapes, format="turtle", **options):
        return "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"


class FakeValidationReport:
    def summary(self):
        return "conforms: True"

    @property
    def violation_count(self):
        return 0


def test_stage_export_exports_iri_ids_and_prints_validation_report(monkeypatch, capsys, tmp_path):
    fake_exporter = FakeExporter()
    fake_shacl = FakeSHACLGenerator()
    fake_report = FakeValidationReport()

    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.setattr(demo, "ROOT", tmp_path)

    # demo imports these *inside* stage_export, so patch the modules
    monkeypatch.setattr(semantica.export, "RDFExporter", lambda: fake_exporter)
    monkeypatch.setattr(semantica.ontology, "SHACLGenerator", lambda: fake_shacl)
    monkeypatch.setattr(
        semantica.ontology.ontology_validator,
        "_run_pyshacl",
        lambda *args, **kwargs: fake_report,
    )

    graph = FakeExportGraph()
    demo.stage_export(graph)

    assert graph.saved_paths
    assert graph.saved_paths[0].endswith("lending_graph.json")

    # exporter received a KG whose entity ids are all IRIs
    assert len(fake_exporter.exported) == 1
    exported_kg = fake_exporter.exported[0]["graph"]
    assert exported_kg["entities"]
    for entity in exported_kg["entities"]:
        assert entity["id"].startswith("https://example.org/lending#")

    # relationship endpoints rewritten too; unmatched endpoint left raw
    rels = exported_kg["relationships"]
    assert rels[0]["source_id"] == "https://example.org/lending#Sunrise-Coffee-Roasters"
    assert rels[1]["target_id"] == "Ghost Endpoint"

    # SHACL generator was driven with the demo ontology
    assert fake_shacl.generated is not None
    assert fake_shacl.generated["name"] == "lending"

    # report summary printed
    out = capsys.readouterr().out
    assert "exported JSON:" in out
    assert "exported RDF:" in out
    assert "SHACL validation: conforms: True" in out
    assert "Neo4j persist skipped" in out
