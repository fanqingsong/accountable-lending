"""Prefect process runner for Application flows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_PREFECT_ROOT = _PKG.parent
_REPO = _PREFECT_ROOT.parent
for _path in (str(_PREFECT_ROOT), str(_REPO)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from prefect import serve

from lending_prefect.flows import application_flow


def main() -> None:
    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
    if not os.environ.get("PREFECT_API_URL", "").strip():
        raise SystemExit("PREFECT_API_URL is required for the process runner")
    serve(
        application_flow.to_deployment(name="lending-application"),
        limit=1,
    )


if __name__ == "__main__":
    main()
