"""Test-suite setup for {{ project_name }}.

Puts `<project>/src` on `sys.path` so tests can `from <module> import ...`
without requiring the project to be pip-installed. Remove this if you
switch to an installed-package layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
