"""Rule: python.xfail_gaming — pytest.mark.xfail(strict=True) hides stub gaming.

Detects two forms:
1. Per-function decorator: `@pytest.mark.xfail(strict=True)` on the test.
2. Module-level: `pytestmark = pytest.mark.xfail(strict=True)` (or a list
   containing such an entry) at the top of the file. Module-level pytestmark
   propagates to every test in the module — same gaming, harder to spot.
"""

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
    tree: ast.AST | None = None,
    **_: object,
) -> Verdict | None:
    evidence = _xfail_strict_evidence(func)
    if evidence is None and tree is not None:
        evidence = _module_pytestmark_xfail_evidence(tree)
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


def _module_pytestmark_xfail_evidence(tree: ast.AST) -> str | None:
    """Walk the module body for `pytestmark = pytest.mark.xfail(strict=True, ...)`.

    Catches the assignment whether the RHS is a single mark call or a list/tuple
    that contains one.
    """
    if not isinstance(tree, ast.Module):
        return None
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not _assigns_to_pytestmark(stmt.targets):
            continue
        if _value_contains_xfail_strict(stmt.value):
            return (
                "module-level pytestmark = pytest.mark.xfail(strict=True) "
                "propagates to every test in the module — same gaming as the "
                "per-function decorator, hidden one level up"
            )
    return None


def _assigns_to_pytestmark(targets: list[ast.expr]) -> bool:
    return any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets)


def _value_contains_xfail_strict(value: ast.expr) -> bool:
    """True when `value` is `pytest.mark.xfail(strict=True)` or a list/tuple containing one."""
    if isinstance(value, ast.Call):
        return _is_xfail_decorator(value.func) and _has_strict_true(value)
    if isinstance(value, ast.List | ast.Tuple):
        return any(_value_contains_xfail_strict(elt) for elt in value.elts)
    return False


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
