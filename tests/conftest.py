"""Shared test configuration for the accountable-lending tests."""

import os
import sys
from pathlib import Path

# backend and lending_prefect live at the project root / prefect/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREFECT_DIR = PROJECT_ROOT / "prefect"
for _path in (str(PREFECT_DIR), str(PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Keep Semantica's interactive progress bars out of test output.
os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
# Unit tests run application_flow in-process; do not submit to a server.
os.environ.pop("PREFECT_API_URL", None)
