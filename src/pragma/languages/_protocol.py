"""Per-language classifier interface.

Each language module under `src/pragma/languages/<lang>/` exposes a
module-level `matches(path)` + `classify_file(path)`; together they
conform to `Classifier`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pragma.verdict import Verdict


@runtime_checkable
class Classifier(Protocol):
    """Each language module conforms to this interface.

    `verify.py` depends on this Protocol — never on a specific language module.
    """

    LANGUAGE: str

    def matches(self, path: Path) -> bool: ...

    def classify_file(self, path: Path) -> list[Verdict]: ...
