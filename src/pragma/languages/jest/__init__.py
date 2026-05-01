"""Jest language plugin for Pragma.

Conforms to `pragma.languages._protocol.Classifier`. Reuses the shared rule
chain in `pragma.languages.vitest.rules` (parameterized by Dialect) plus a
jest-only `test.failing` rule that has no Vitest analog.
"""

from __future__ import annotations

import re
from pathlib import Path

from pragma.languages._jsts_core import classify_with_dialect
from pragma.languages._jsts_core.dialect import JEST_DIALECT
from pragma.verdict import Verdict

LANGUAGE = "jest"

_EXTS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"})
_TEST_NAME_PATTERN = re.compile(r"(?:^|/)(?:.+\.(?:test|spec)\.|tests?/|__tests__/)")
_VITEST_IMPORT = re.compile(rb'from\s+["\']vitest["\']|require\(\s*["\']vitest["\']')


def matches(path: Path) -> bool:
    """True when path is a Jest test file.

    Path-based matching only — Jest tests typically use auto-injected globals
    rather than importing `@jest/globals`. To stay disjoint from Vitest, we
    explicitly REJECT files that import from "vitest" (those are vitest's).
    """
    if path.suffix not in _EXTS:
        return False
    if not _TEST_NAME_PATTERN.search(str(path)):
        return False
    try:
        head = path.read_bytes()[:4096]
    except OSError:
        return False
    return not _VITEST_IMPORT.search(head)


def classify_file(path: Path) -> list[Verdict]:
    """Classify every Jest test call in `path`."""
    from pragma.languages.jest.rules.test_failing import classify as test_failing_classify

    return classify_with_dialect(path, JEST_DIALECT, extra_rules=(test_failing_classify,))
