"""Load a ContextGraph snapshot. Must not import Prefect."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.paths import GRAPH_JSON


def load_graph(path: Optional[Path] = None):
    """Load a ContextGraph from JSON, or return an empty graph."""
    from semantica.context import ContextGraph

    dest = Path(path) if path is not None else GRAPH_JSON
    graph = ContextGraph()
    if dest.is_file():
        graph.load_from_file(str(dest))
    return graph
