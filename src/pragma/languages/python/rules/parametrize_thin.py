"""Rule: python.parametrize_thin — @parametrize with ≤1 case claims breadth."""

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
) -> Verdict | None:
    evidence = _parametrize_thin_evidence(func)
    if evidence:
        return Verdict(kind="python.parametrize_thin", evidence=evidence, test_name=test_name)
    return None


def _parametrize_thin_evidence(func: ast.FunctionDef) -> str:
    """`@pytest.mark.parametrize` whose values list has 0 or 1 cases."""
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        if not _is_parametrize_decorator(dec.func):
            continue
        if len(dec.args) < 2:
            continue
        values = dec.args[1]
        count = _count_parametrize_cases(values)
        if count is not None and count <= 1:
            return f"@parametrize with N={count} case(s) claims breadth"
    return ""


def _is_parametrize_decorator(func: ast.expr) -> bool:
    """Match `pytest.mark.parametrize` or `mark.parametrize` or `parametrize`."""
    if isinstance(func, ast.Attribute) and func.attr == "parametrize":
        return True
    return isinstance(func, ast.Name) and func.id == "parametrize"


def _count_parametrize_cases(values: ast.expr) -> int | None:
    """Return the number of cases in a parametrize values list, or None
    when we can't tell statically (e.g. the values are a Name reference).
    """
    if isinstance(values, ast.List | ast.Tuple):
        return len(values.elts)
    return None
