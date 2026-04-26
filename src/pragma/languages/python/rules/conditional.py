"""Rule: python.conditional — every assertion lives inside a conditional branch."""

from __future__ import annotations

import ast

from pragma.languages.python.rules._shared import _is_with_raises, node_inside_any
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
    if _all_assertions_conditional(func):
        return Verdict(
            kind="python.conditional",
            evidence="all assertions live inside conditional branches the inputs never enter",
            test_name=test_name,
        )
    return None


def _all_assertions_conditional(func: ast.FunctionDef) -> bool:
    """True when every assertion (and pytest.raises with-block) is nested
    inside an `if`/`for`/`while`. Indicates the assertions may never run.

    Conservative: requires at least one assertion AND every one to be
    nested. A test with one top-level assert + one conditional assert is
    not flagged.
    """
    asserts = [a for a in ast.walk(func) if isinstance(a, ast.Assert)]
    raises_withs = [n for n in ast.walk(func) if isinstance(n, ast.With) and _is_with_raises(n)]
    all_assertion_nodes = asserts + raises_withs
    if not all_assertion_nodes:
        return False
    guards = [n for n in ast.walk(func) if isinstance(n, ast.If | ast.For | ast.While)]
    if not guards:
        return False
    return all(node_inside_any(a, guards) for a in all_assertion_nodes)
