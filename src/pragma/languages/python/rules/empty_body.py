"""Rule: python.empty_body — test body has no assertion and no pytest.raises."""

from __future__ import annotations

import ast

from pragma.languages.python.rules._shared import has_raises_assertion
from pragma.verdict import Verdict


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    **_: object,
) -> Verdict | None:
    if _empty_body(func):
        return Verdict(
            kind="python.empty_body",
            evidence="test body has no assertion and no pytest.raises",
            test_name=test_name,
        )
    return None


def _empty_body(func: ast.FunctionDef) -> bool:
    """Test body has no assertion and no pytest.raises.

    Allows the body to contain helper calls, comments, and a docstring;
    flags only when *no* assertion machinery is present at all.
    """
    has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(func))
    if has_assert:
        return False
    return not has_raises_assertion(func)
