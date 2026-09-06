"""Write ContextGraph JSON. lending-api only loads this file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.application import GRAPH_JSON


def write_graph_snapshot(graph, path: Optional[Path] = None) -> Path:
    """Atomically write ContextGraph JSON. A failed write leaves the old file."""
    dest = Path(path) if path is not None else GRAPH_JSON
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    wrote = False
    if hasattr(graph, "save_to_file"):
        graph.save_to_file(str(tmp))
        wrote = tmp.is_file()
    if not wrote:
        payload = graph.to_dict() if hasattr(graph, "to_dict") else {}
        tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(dest)
    return dest
