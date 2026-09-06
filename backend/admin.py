"""Knowledge Explorer — the lending admin UI.

Loads the latest ContextGraph snapshot and serves Semantica Explorer on
port 8000. The JSON API is ``python -m backend.api``; the lending UI is
served separately.
"""

from __future__ import annotations

import os
import sys

from backend.paths import GRAPH_JSON
from backend.snapshot import load_or_build_graph, note as _note

__all__ = ["GRAPH_JSON", "load_or_build_graph", "load_snapshot_session", "main"]


def load_snapshot_session():
    """Load Explorer's GraphSession from the ContextGraph snapshot only."""
    if not GRAPH_JSON.is_file():
        raise FileNotFoundError(f"ContextGraph snapshot missing: {GRAPH_JSON}")
    from semantica.explorer.session import GraphSession

    session = GraphSession.from_file(str(GRAPH_JSON))
    _note(f"Explorer loaded snapshot {GRAPH_JSON}")
    return session


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
