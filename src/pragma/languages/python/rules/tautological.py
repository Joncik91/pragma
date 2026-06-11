"""Rule: python.tautological — assertion is True/x == x/1 == 1."""

from __future__ import annotations

import ast
import re

from pragma.verdict import Verdict

# Test names that legitimately assert reflexivity / __eq__ self-equality.
_REFLEXIVITY_NAME = re.compile(r"reflexiv|__eq__|_eq_|equals_self|eq_self")


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    **_: object,
) -> Verdict | None:
    evidence = _tautological_evidence(func)
    if not evidence:
        return None
    # A `x == x` assertion in a reflexivity / __eq__ test is exercising the
    # type's real equality semantics, not gaming. Downgrade to a non-blocking
    # warn (only for the x==x shape; constant-truthy asserts still block).
    if _is_reflexivity_test(test_name, func):
        return Verdict(
            kind="python.tautological_warn",
            evidence=(
                f"{evidence}; downgraded — test name implies a reflexivity / "
                "__eq__ check, so self-equality exercises real behavior"
            ),
            test_name=test_name,
        )
    return Verdict(kind="python.tautological", evidence=evidence, test_name=test_name)


def _is_reflexivity_test(test_name: str, func: ast.FunctionDef) -> bool:
    """True when the name signals a reflexivity/__eq__ test AND every flagged
    assertion is the `x == x` shape (not a constant-truthy tautology)."""
    if not _REFLEXIVITY_NAME.search(test_name):
        return False
    flagged = [a for a in ast.walk(func) if isinstance(a, ast.Assert) and _classify_assert_taut(a)]
    return bool(flagged) and all(_is_x_eq_x(a.test) for a in flagged)


def _tautological_evidence(func: ast.FunctionDef) -> str:
    asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
    # An empty body (no asserts, no pytest.raises) is now caught by
    # `_empty_body` further down the priority list as a `weak` verdict.
    # `tautological` only fires for actual constant-truthy / x==x asserts.
    if not asserts:
        return ""
    for a in asserts:
        ev = _classify_assert_taut(a)
        if ev:
            return ev
    return ""


def _classify_assert_taut(node: ast.Assert) -> str:
    """Detect a tautological assertion node. Empty if not tautological."""
    test = node.test
    if _is_truthy_literal(test):
        return f"`assert {ast.unparse(test)}` is a constant truthy"
    if _is_x_eq_x(test):
        assert isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
        return f"`{test.left.id} == {test.left.id}` is x == x tautology"
    if _is_const_eq_same_const(test):
        return f"`{ast.unparse(test)}` is constant == same-constant tautology"
    return ""


def _is_truthy_literal(test: ast.expr) -> bool:
    return isinstance(test, ast.Constant) and bool(test.value)


def _is_x_eq_x(test: ast.expr) -> bool:
    if not _is_simple_eq(test):
        return False
    assert isinstance(test, ast.Compare)
    left, right = test.left, test.comparators[0]
    return isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id


def _is_const_eq_same_const(test: ast.expr) -> bool:
    if not _is_simple_eq(test):
        return False
    assert isinstance(test, ast.Compare)
    left, right = test.left, test.comparators[0]
    return (
        isinstance(left, ast.Constant)
        and isinstance(right, ast.Constant)
        and left.value == right.value
    )


def _is_simple_eq(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
    )
