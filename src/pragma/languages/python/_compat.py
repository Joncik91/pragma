"""v1.x classify_test shim — keeps tests/test_classifier.py compiling.

The new architecture orchestrates classification at the file level, but
the old per-test-function `classify_test(source, test_name=..., expected=..., ...)`
call shape is too useful for unit tests to lose. This shim re-runs the
RULES list against an in-memory AST and returns the first non-None
verdict, with the same Verdict shape (just `python.`-prefixed).
"""

from __future__ import annotations

import ast

from pragma.languages.python.rules import RULES
from pragma.verdict import Verdict


def classify_test(
    source: str,
    *,
    test_name: str,
    expected: str,
    target_module: str | None = None,
    target_symbol: str | None = None,
) -> Verdict:
    tree = ast.parse(source)
    func = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == test_name
        ),
        None,
    )
    if func is None:
        return Verdict(
            kind="python.mismatched",
            evidence=f"no function named {test_name!r} in source",
            test_name=test_name,
        )
    ctx = {
        "test_name": test_name,
        "expected": expected,
        "target_module": target_module,
        "target_symbol": target_symbol,
        "tree": tree,
        "file_path": None,
    }
    for rule in RULES:
        verdict = rule(func, **ctx)
        if verdict is not None:
            return verdict
    return Verdict(
        kind="python.verified",
        evidence="assertion passes runtime-derived value through real comparison",
        test_name=test_name,
    )
