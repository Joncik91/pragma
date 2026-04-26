"""Pytest conftest for coverage_gated fixtures.

Inserts the `src/` subdirectory into sys.path so fixtures can use
bare `from inventory import ...` imports. This is necessary because:
1. `infer_target` in the inference layer filters out modules that start
   with `tests.` (they're not production targets).
2. The coverage runner spawns pytest with cwd=this directory, so a
   sys.path insert here makes the import work in both contexts.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
