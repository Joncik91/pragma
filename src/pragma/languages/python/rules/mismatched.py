"""Rule: python.mismatched — expected=reject but body has no pytest.raises / except."""

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
    if expected == "reject" and not has_raises_assertion(func):
        return Verdict(
            kind="python.mismatched",
            evidence="expected=reject but no pytest.raises / except assertion in body",
            test_name=test_name,
        )
    return None
