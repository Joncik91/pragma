"""Language registry — populated as language modules ship."""

from __future__ import annotations

from pragma.languages import python as python_lang
from pragma.languages import vitest as vitest_lang
from pragma.languages._protocol import Classifier

REGISTRY: list[Classifier] = [python_lang, vitest_lang]
