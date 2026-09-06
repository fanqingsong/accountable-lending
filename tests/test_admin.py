"""Tests for admin graph loading. Pipeline stages are faked."""

import semantica.context

from backend import admin, snapshot


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

    monkeypatch.setattr(snapshot, "GRAPH_JSON", saved)
    monkeypatch.delenv("LENDING_REBUILD", raising=False)
    monkeypatch.setattr(semantica.context, "ContextGraph", FakeGraph)
    monkeypatch.setattr(
        "backend.prefect_api.submit_seed_run",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not submit")),
    )

    loaded = snapshot.load_or_build_graph()
    assert loaded.path == str(saved)


def test_load_or_build_graph_submits_seed_when_missing(tmp_path, monkeypatch):
    calls = []

    class FakeGraph:
        pass

    monkeypatch.setattr(snapshot, "GRAPH_JSON", tmp_path / "missing.json")
    monkeypatch.setenv("LENDING_REBUILD", "0")
    monkeypatch.setattr(
        "backend.prefect_api.submit_seed_run",
        lambda **kwargs: calls.append("seed"),
    )
    monkeypatch.setattr("backend.application.load_graph", lambda path=None: FakeGraph())
    monkeypatch.setattr("backend.application.ensure_seed_application", lambda graph: None)

    built = snapshot.load_or_build_graph()
    assert isinstance(built, FakeGraph)
    assert calls == ["seed"]


def test_rebuild_flag_submits_seed(tmp_path, monkeypatch):
    saved = tmp_path / "lending_graph.json"
    saved.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(snapshot, "GRAPH_JSON", saved)
    monkeypatch.setenv("LENDING_REBUILD", "1")

    calls = []
    monkeypatch.setattr(
        "backend.prefect_api.submit_seed_run",
        lambda **kwargs: calls.append(("seed", kwargs.get("wait"))),
    )
    monkeypatch.setattr("backend.application.load_graph", lambda path=None: object())
    monkeypatch.setattr("backend.application.ensure_seed_application", lambda graph: None)

    snapshot.load_or_build_graph()
    assert calls == [("seed", True)]
    assert not saved.is_file()


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

    monkeypatch.setattr(
        "backend.prefect_api.submit_seed_run",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Explorer must not rebuild")
        ),
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
