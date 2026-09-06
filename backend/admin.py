"""Knowledge Explorer — the lending admin UI.

Loads the latest ContextGraph snapshot and serves Semantica Explorer on
port 8000. The JSON API is ``python -m backend.api``; the lending UI is
served separately.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH_JSON = ROOT / "exports" / "lending_graph.json"


def _note(message: str) -> None:
    print(f"    {message}", flush=True)


def load_snapshot_session():
    """Load Explorer's GraphSession from the ContextGraph snapshot only."""
    if not GRAPH_JSON.is_file():
        raise FileNotFoundError(f"ContextGraph snapshot missing: {GRAPH_JSON}")
    from semantica.explorer.session import GraphSession

    session = GraphSession.from_file(str(GRAPH_JSON))
    _note(f"Explorer loaded snapshot {GRAPH_JSON}")
    return session


def load_or_build_graph():
    """Return a ContextGraph: rebuild the pipeline, or reload the saved JSON."""
    from backend.pipeline import ensure_seed_application

    rebuild = os.environ.get("LENDING_REBUILD", "").strip().lower() in {"1", "true", "yes"}
    if GRAPH_JSON.is_file() and not rebuild:
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.load_from_file(str(GRAPH_JSON))
        _note(f"loaded graph from {GRAPH_JSON}")
        ensure_seed_application(graph)
        return graph

    from backend.pipeline import build_seed_graph

    _note("running lending pipeline (ingest → decide → export)")
    return build_seed_graph()


def main() -> None:
    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
    os.environ.setdefault("SEMANTICA_ALLOW_ANONYMOUS", "true")

    print()
    print("Accountable Lending — admin UI (Knowledge Explorer)")
    print()

    try:
        session = load_snapshot_session()
    except FileNotFoundError as exc:
        print(f"Explorer needs a snapshot from lending-api: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        import uvicorn
        from semantica.explorer.app import create_app
    except ImportError as exc:
        print(
            f"Explorer extra is missing: {exc}\n"
            'Install with: pip install "semantica[explorer]"',
            file=sys.stderr,
        )
        sys.exit(1)

    host = os.environ.get("EXPLORER_HOST", "0.0.0.0")
    port = int(os.environ.get("EXPLORER_PORT", "8000"))
    app = create_app(session=session)
    _note(f"Explorer listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
