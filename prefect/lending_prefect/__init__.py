"""Prefect adapter package. Does not replace the installed Prefect library."""

from __future__ import annotations

import sys
from pathlib import Path


def _bind_installed_prefect() -> None:
    """Keep `import prefect` on the PyPI package, not this folder."""
    repo = Path(__file__).resolve().parents[2]
    existing = sys.modules.get("prefect")
    origin = getattr(existing, "__file__", None) if existing is not None else None
    if origin:
        installed_path = Path(origin).resolve()
        if repo not in installed_path.parents:
            return
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != repo]
    sys.modules.pop("prefect", None)
    import prefect as installed

    sys.path[:] = saved
    sys.modules["prefect"] = installed


_bind_installed_prefect()
