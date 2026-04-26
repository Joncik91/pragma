"""Rule: python.weak — weak assertion when expected=success."""

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
    if expected == "success":
        evidence = _weak_assertion_evidence(func)
        if evidence:
            return Verdict(kind="python.weak", evidence=evidence, test_name=test_name)
    return None


def _weak_assertion_evidence(func: ast.FunctionDef) -> str:
    asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
    if not asserts:
        return ""
    if any(_is_specific_assertion(a) for a in asserts):
        return ""
    for a in asserts:
        ev = _classify_assert_weak(a.test)
        if ev:
            return ev
    return ""


def _is_specific_assertion(node: ast.Assert) -> bool:
    """A specific assertion checks against a concrete expected value."""
    test = node.test
    if _is_specific_compare(test):
        return True
    return _is_isinstance_call(test)


def _is_specific_compare(test: ast.expr) -> bool:
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
        return False
    op = test.ops[0]
    if isinstance(op, ast.Eq | ast.NotEq):
        return any(not _is_none_constant(c) for c in test.comparators)
    return isinstance(op, ast.In | ast.NotIn)


def _is_none_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_isinstance_call(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
    )


def _classify_assert_weak(test: ast.expr) -> str:
    if _is_is_not_none(test):
        return "`assert x is not None` is weak when expected=success"
    if _is_len_check(test):
        return f"`{ast.unparse(test)}` is a length check, weak when expected=success"
    if isinstance(test, ast.Name):
        return f"`assert {test.id}` is a truthy check, weak when expected=success"
    return ""


def _is_is_not_none(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and _is_none_constant(test.comparators[0])
    )


def _is_len_check(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Call)
        and isinstance(test.left.func, ast.Name)
        and test.left.func.id == "len"
    )
