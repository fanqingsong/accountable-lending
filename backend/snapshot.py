"""Load or seed the ContextGraph snapshot. Prefect-aware; Application stays free of it."""

from __future__ import annotations

import os

from backend.paths import GRAPH_JSON


def note(message: str) -> None:
    print(f"    {message}", flush=True)


def load_or_build_graph():
    """Return a ContextGraph: submit seed via Prefect API if needed, else reload JSON."""
    from backend.application import ensure_seed_application, load_graph
    from backend.prefect_api import submit_seed_run

    rebuild = os.environ.get("LENDING_REBUILD", "").strip().lower() in {"1", "true", "yes"}
    if GRAPH_JSON.is_file() and not rebuild:
        note(f"loaded graph from {GRAPH_JSON}")
        graph = load_graph(GRAPH_JSON)
        ensure_seed_application(graph)
        return graph
    if GRAPH_JSON.is_file() and rebuild:
        GRAPH_JSON.unlink()
    note("submitting application_flow seed via Prefect API")
    submit_seed_run(snapshot_path=str(GRAPH_JSON), wait=True)
    graph = load_graph(GRAPH_JSON)
    ensure_seed_application(graph)
    return graph
