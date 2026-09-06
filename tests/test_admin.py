"""Tests for admin graph loading. Pipeline stages are faked."""

import semantica.context

from backend import admin


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

    import backend.pipeline as pipeline

    monkeypatch.setattr(pipeline, "build_seed_graph", lambda: calls.append("seed") or FakeGraph())

    built = admin.load_or_build_graph()
    assert isinstance(built, FakeGraph)
    assert calls == ["seed"]


def test_rebuild_flag_ignores_existing_snapshot(tmp_path, monkeypatch):
    saved = tmp_path / "lending_graph.json"
    saved.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(admin, "GRAPH_JSON", saved)
    monkeypatch.setenv("LENDING_REBUILD", "1")

    import backend.pipeline as pipeline

    calls = []
    monkeypatch.setattr(pipeline, "build_seed_graph", lambda: calls.append("seed") or object())

    admin.load_or_build_graph()
    assert calls == ["seed"]


def test_explorer_requires_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(admin, "GRAPH_JSON", tmp_path / "missing.json")
    try:
        admin.load_snapshot_session()
        raise AssertionError("missing snapshot should fail")
    except FileNotFoundError as exc:
        assert "snapshot" in str(exc).lower()


def test_explorer_loads_snapshot_without_rebuild(tmp_path, monkeypatch):
    saved = tmp_path / "lending_graph.json"
    saved.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(admin, "GRAPH_JSON", saved)

    import backend.pipeline as pipeline

    monkeypatch.setattr(
        pipeline,
        "build_seed_graph",
        lambda: (_ for _ in ()).throw(AssertionError("Explorer must not rebuild")),
    )

    class FakeSession:
        @classmethod
        def from_file(cls, path):
            obj = cls()
            obj.path = path
            return obj

    import semantica.explorer.session as explorer_session

    monkeypatch.setattr(explorer_session, "GraphSession", FakeSession)

    session = admin.load_snapshot_session()
    assert session.path == str(saved)
