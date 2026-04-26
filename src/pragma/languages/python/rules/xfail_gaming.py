"""Rule: python.xfail_gaming — pytest.mark.xfail(strict=True) hides stub gaming."""

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
    evidence = _xfail_strict_evidence(func)
    if evidence is None:
        return None
    return Verdict(
        kind="python.xfail_gaming",
        evidence=evidence,
        test_name=test_name,
    )


def _xfail_strict_evidence(func: ast.FunctionDef) -> str | None:
    """Return evidence string when the test is decorated with xfail(strict=True)."""
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        if not _is_xfail_decorator(dec.func):
            continue
        if _has_strict_true(dec):
            return "@pytest.mark.xfail(strict=True) makes a failing stub pass CI"
    return None


def _is_xfail_decorator(callee: ast.expr) -> bool:
    """Match `pytest.mark.xfail` / `mark.xfail` / `xfail`."""
    if isinstance(callee, ast.Attribute) and callee.attr == "xfail":
        return True
    return isinstance(callee, ast.Name) and callee.id == "xfail"


def _has_strict_true(call: ast.Call) -> bool:
    """True when the decorator has strict=True."""
    for kw in call.keywords:
        if kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False
