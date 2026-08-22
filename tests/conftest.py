"""Shared test configuration for the accountable-lending demo tests."""

import os
import sys
from pathlib import Path

# demo.py lives at the project root; make it importable from the tests dir.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep Semantica's interactive progress bars out of test output.
os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
