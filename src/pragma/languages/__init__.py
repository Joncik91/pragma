"""Language registry — populated as language modules ship."""

from __future__ import annotations

from pragma.languages import jest as jest_lang
from pragma.languages import python as python_lang
from pragma.languages import vitest as vitest_lang
from pragma.languages._protocol import Classifier

# Order matters: vitest's `matches()` requires `from "vitest"` import; jest's
# `matches()` rejects files with that import. So vitest claims its files first
# and jest catches the rest. The verify orchestrator short-circuits on first
# match.
REGISTRY: list[Classifier] = [python_lang, vitest_lang, jest_lang]
