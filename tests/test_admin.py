"""Tests for admin graph loading. Pipeline stages are faked."""

import semantica.context

from app import admin


def test_load_or_build_graph_reuses_saved_json(tmp_path, monkeypatch):
    saved = tmp_path / "lending_graph.json"
    saved.write_text("{}", encoding="utf-8")

    class FakeGraph:
        def load_from_file(self, path):
            self.path = path

        def to_dict(self):
            return {"nodes": []}

        def add_node(self, *args, **kwargs):
            return None

        def add_edge(self, *args, **kwargs):
            return None

    monkeypatch.setattr(admin, "GRAPH_JSON", saved)
    monkeypatch.delenv("LENDING_REBUILD", raising=False)
    monkeypatch.setattr(semantica.context, "ContextGraph", FakeGraph)

    loaded = admin.load_or_build_graph()
    assert loaded.path == str(saved)


def test_load_or_build_graph_runs_pipeline_when_missing(tmp_path, monkeypatch):
    calls = []

    class FakeGraph:
        pass

    monkeypatch.setattr(admin, "GRAPH_JSON", tmp_path / "missing.json")
    monkeypatch.setenv("LENDING_REBUILD", "0")

    import app.pipeline as pipeline

    monkeypatch.setattr(pipeline, "build_seed_graph", lambda: calls.append("seed") or FakeGraph())

    built = admin.load_or_build_graph()
    assert isinstance(built, FakeGraph)
    assert calls == ["seed"]
