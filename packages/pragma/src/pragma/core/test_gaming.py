"""AST test-gaming detector — REQ-046.

The real Pragma thesis: AI tends to write tests that *pass* without
actually verifying behaviour. This module classifies each test in
one of five verdicts so the gate can refuse gamed tests.

Verdicts:
- `verified`: the assertion calls the production target and asserts
  on its return value or raised exception.
- `tautological`: the assertion is `True`/`x == x`/`1 == 1` or only
  asserts on values the test itself set up.
- `mocked-away`: `mock.patch` targets the function under test
  (the production symbol the manifest says this REQ exercises),
  not its dependencies.
- `weak`: assertion is `is not None`/`> 0`/`len(...) >= 1` when the
  manifest says `expected=success` (caller wanted a specific value).
  Warning, not refuse — judgment call.
- `mismatched`: manifest says `expected=reject` but the test body
  has no `pytest.raises` / `except` assertion proving rejection.

The detector is conservative on `verified`: when in doubt about
whether a test is gamed, lean toward flagging it. False positives
(real tests flagged) are surfaced as warnings the user can ack;
false negatives (gamed tests passing) defeat the whole point.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    """One per test function."""

    kind: str  # verified | tautological | mocked-away | weak | mismatched
    evidence: str
    test_name: str

    def __repr__(self) -> str:
        return f"Verdict(kind={self.kind!r}, evidence={self.evidence!r}, test={self.test_name!r})"


def classify_test(
    source: str,
    *,
    test_name: str,
    expected: str,
    target_module: str | None = None,
    target_symbol: str | None = None,
) -> Verdict:
    """Classify a single test function from its source text."""
    tree = ast.parse(source)
    func = _find_test_func(tree, test_name)
    if func is None:
        return Verdict(
            kind="mismatched",
            evidence=f"no function named {test_name!r} in source",
            test_name=test_name,
        )
    return _classify_in_order(func, test_name, expected, target_module, target_symbol)


def _classify_in_order(
    func: ast.FunctionDef,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
) -> Verdict:
    """Classification order: mocked-away > mismatched > tautological > weak > verified."""
    if (
        target_module
        and target_symbol
        and _mocks_function_under_test(func, target_module, target_symbol)
    ):
        return Verdict(
            kind="mocked-away",
            evidence=f"mock.patch on {target_module}.{target_symbol} (the function under test)",
            test_name=test_name,
        )
    if expected == "reject" and not _has_raises_assertion(func):
        return Verdict(
            kind="mismatched",
            evidence="expected=reject but no pytest.raises / except assertion in body",
            test_name=test_name,
        )
    taut = _tautological_evidence(func)
    if taut:
        return Verdict(kind="tautological", evidence=taut, test_name=test_name)
    if expected == "success":
        weak = _weak_assertion_evidence(func)
        if weak:
            return Verdict(kind="weak", evidence=weak, test_name=test_name)
    return Verdict(
        kind="verified",
        evidence="assertion passes runtime-derived value through real comparison",
        test_name=test_name,
    )


def _find_test_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _tautological_evidence(func: ast.FunctionDef) -> str:
    asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
    if not asserts:
        return "test body has no assertions"
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


def _has_raises_assertion(func: ast.FunctionDef) -> bool:
    """True when the body uses `pytest.raises` or an `except` block."""
    for node in ast.walk(func):
        if _is_with_raises(node):
            return True
        if isinstance(node, ast.Try) and node.handlers:
            return True
    return False


def _is_with_raises(node: ast.AST) -> bool:
    if not isinstance(node, ast.With):
        return False
    return any(_is_raises_call(item.context_expr) for item in node.items)


def _is_raises_call(expr: ast.expr) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "raises"
    )


def _mocks_function_under_test(
    func: ast.FunctionDef,
    target_module: str,
    target_symbol: str,
) -> bool:
    """True when the test patches the production target."""
    target = f"{target_module}.{target_symbol}"
    if any(_is_patch_with_target(n, target) for n in ast.walk(func)):
        return True
    return any(_is_patch_with_target(d, target) for d in func.decorator_list)


def _is_patch_with_target(node: ast.AST, target: str) -> bool:
    if not isinstance(node, ast.Call) or not _is_patch_call(node):
        return False
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return False
    return node.args[0].value == target


def _is_patch_call(node: ast.Call) -> bool:
    """True for `patch(...)` / `mock.patch(...)` / `unittest.mock.patch(...)`."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "patch":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "patch"
