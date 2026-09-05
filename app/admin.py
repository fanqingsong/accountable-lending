"""Knowledge Explorer — the lending admin UI.

Loads the latest ContextGraph (rebuilds from ``data/`` when needed), writes it
to Neo4j, and serves Semantica Explorer on port 8000. Case import lives at
``/lending``; GraphRAG retrieve lives at ``/lending/retrieve``;
chat (LLM generation only) lives at ``/lending/chat``;
ontology / SHACL lives at ``/lending/ontology``.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH_JSON = ROOT / "exports" / "lending_graph.json"


def _note(message: str) -> None:
    print(f"    {message}", flush=True)


def load_or_build_graph():
    """Return a ContextGraph: rebuild the pipeline, or reload the saved JSON."""
    from app.pipeline import ensure_seed_application

    rebuild = os.environ.get("LENDING_REBUILD", "").strip().lower() in {"1", "true", "yes"}
    if GRAPH_JSON.is_file() and not rebuild:
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.load_from_file(str(GRAPH_JSON))
        _note(f"loaded graph from {GRAPH_JSON}")
        ensure_seed_application(graph)
        return graph

    from app.pipeline import build_seed_graph

    _note("running lending pipeline (ingest → decide → export)")
    return build_seed_graph()


def main() -> None:
    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
    os.environ.setdefault("SEMANTICA_ALLOW_ANONYMOUS", "true")

    print()
    print("Accountable Lending — admin UI (Knowledge Explorer)")
    print()

    graph = load_or_build_graph()

    from app.ontology import validate_graph
    from app.retrieve import connect_vector_store, index_graph
    from app.stores import persist_graph

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

    try:
        import uvicorn
        from semantica.explorer.app import create_app
        from semantica.explorer.session import GraphSession
    except ImportError as exc:
        print(
            f"Explorer extra is missing: {exc}\n"
            'Install with: pip install "semantica[explorer]"',
            file=sys.stderr,
        )
        sys.exit(1)

    host = os.environ.get("EXPLORER_HOST", "0.0.0.0")
    port = int(os.environ.get("EXPLORER_PORT", "8000"))
    from app.routes import attach_lending_routes

    session = GraphSession(graph)
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
    app = create_app(session=session)
    attach_lending_routes(app, session, vector_store=vector_ref)
    _note(f"admin UI listening on http://{host}:{port}")
    _note(f"case import: http://{host}:{port}/lending")
    _note(f"retrieve:    http://{host}:{port}/lending/retrieve")
    _note(f"chat:        http://{host}:{port}/lending/chat")
    _note(f"ontology:    http://{host}:{port}/lending/ontology")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
