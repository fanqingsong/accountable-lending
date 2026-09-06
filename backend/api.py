"""Lending JSON API — no HTML, no Explorer."""

from __future__ import annotations

import os
import threading

from backend.admin import load_or_build_graph, _note


def main() -> None:
    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

    print()
    print("Accountable Lending — JSON API")
    print()

    graph = load_or_build_graph()

    from backend.ontology import validate_graph
    from backend.retrieve import connect_vector_store, index_graph
    from backend.routes import attach_lending_routes
    from backend.stores import persist_graph
    from fastapi import FastAPI
    import uvicorn

    schema = validate_graph(graph)
    if schema["conforms"]:
        _note(f"schema: graph conforms ({schema['checked']} nodes)")
    else:
        _note(f"!! schema: {len(schema['violations'])} violation(s)")

    result = persist_graph(graph)
    if result.get("skipped"):
        _note("Neo4j persist skipped (NEO4J_URI not set)")
    else:
        _note(
            f"persisted LPG to Neo4j: {result['nodes']} nodes, "
            f"{result['edges']} edges"
        )

    class Session:
        def __init__(self, graph):
            self.graph = graph

        def rebuild_search_index(self):
            return None

    session = Session(graph)
    vector_ref = {"store": None}

    def _connect_and_index() -> None:
        try:
            store = connect_vector_store()
            vector_ref["store"] = store
            if store is not None:
                indexed = index_graph(graph, store)
                _note(f"indexed {indexed} chunks into Qdrant")
        except Exception as exc:  # noqa: BLE001 — retrieve still works without vectors
            _note(f"!! Qdrant index skipped: {type(exc).__name__}: {exc}")
            vector_ref["store"] = None

    threading.Thread(target=_connect_and_index, daemon=True, name="qdrant-index").start()

    app = FastAPI(title="Accountable Lending API")
    attach_lending_routes(app, session, vector_store=vector_ref)

    host = os.environ.get("LENDING_API_HOST", "0.0.0.0")
    port = int(os.environ.get("LENDING_API_PORT", "8001"))
    _note(f"lending-api listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
