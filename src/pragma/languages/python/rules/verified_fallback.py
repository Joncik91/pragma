"""Rule: python.verified — fallback verdict when no other rule fires."""

from __future__ import annotations

import ast

from pragma.verdict import Verdict


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    **_: object,
) -> Verdict:
    return Verdict(
        kind="python.verified",
        evidence="assertion passes runtime-derived value through real comparison",
        test_name=test_name,
    )
