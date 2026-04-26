"""AST test-gaming detector.

Classifies each test in one of eleven verdicts so the gate can refuse
gamed tests. Five verdicts BLOCK the tool call (the test is doing
something dishonest); three verdicts WARN (the test is suspicious but
might be intentional); one verdict PASSES.

Blocking verdicts:
- `mocked-away`: `mock.patch` targets the function under test.
- `monkeypatched`: `monkeypatch.setattr` targets the function under test.
- `swallowed`: `try: <call>; except: pass` swallows the call under test.
- `skipped`: `pytest.skip(...)` / `xfail` smuggled at top of body.
- `mismatched`: `expected=reject` but body has no `pytest.raises`/`except`.
- `conditional`: every assertion lives inside an if/for/while branch.
- `tautological`: assertion is `True`/`x == x`/`1 == 1`.

Warning (non-blocking) verdicts:
- `empty_body`: test body has no assertion and no pytest.raises.
- `parametrize_thin`: `@parametrize` with ≤1 case claims breadth.
- `weak`: `is not None`/`len > 0` when an exact value was expected.

Pass verdict:
- `verified`: assertion calls the production target and asserts on its
  return value or raised exception.

The detector is conservative: when in doubt, lean toward flagging.
False positives surface as warnings the user can ack; false negatives
(gamed tests passing) defeat the whole point.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    """One per test function."""

    kind: str  # see module docstring for the full set of 11 verdict kinds.
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
    """Classification order: mocked-away > monkeypatched > swallowed > skipped >
    mismatched > conditional > tautological > empty_body > parametrize_thin >
    weak > verified."""
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
    if (
        target_module
        and target_symbol
        and _monkeypatches_function_under_test(func, target_module, target_symbol)
    ):
        return Verdict(
            kind="monkeypatched",
            evidence=(
                f"monkeypatch.setattr on {target_module}.{target_symbol} (the function under test)"
            ),
            test_name=test_name,
        )
    if _swallows_call(func):
        return Verdict(
            kind="swallowed",
            evidence="`try: <call>; except: pass` swallows the call under test",
            test_name=test_name,
        )
    skipped_evidence = _skipped_evidence(func)
    if skipped_evidence:
        return Verdict(kind="skipped", evidence=skipped_evidence, test_name=test_name)
    if expected == "reject" and not _has_raises_assertion(func):
        return Verdict(
            kind="mismatched",
            evidence="expected=reject but no pytest.raises / except assertion in body",
            test_name=test_name,
        )
    if _all_assertions_conditional(func):
        return Verdict(
            kind="conditional",
            evidence="all assertions live inside conditional branches the inputs never enter",
            test_name=test_name,
        )
    taut = _tautological_evidence(func)
    if taut:
        return Verdict(kind="tautological", evidence=taut, test_name=test_name)
    if _empty_body(func):
        return Verdict(
            kind="empty_body",
            evidence="test body has no assertion and no pytest.raises",
            test_name=test_name,
        )
    thin = _parametrize_thin_evidence(func)
    if thin:
        return Verdict(kind="parametrize_thin", evidence=thin, test_name=test_name)
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


# ---------------------------------------------------------------------------
# v1.1.0 detectors: swallowed, skipped, conditional, monkeypatched,
# empty_body, parametrize_thin.
# ---------------------------------------------------------------------------


def _swallows_call(func: ast.FunctionDef) -> bool:
    """True when the body wraps the system-under-test in a try/except: pass.

    Conservative: only fires when the function has at least one `Try` whose
    handler body is just `pass` (or `pass` + a docstring), AND the function
    has no plain `assert` statements outside that try. A test that does
    real work after the try is not swallowed.
    """
    tries_with_pass_only = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Try)
        and n.handlers
        and all(_handler_only_passes(h) for h in n.handlers)
    ]
    if not tries_with_pass_only:
        return False
    # If the function has any `assert` outside the swallowing tries, it's
    # not just-swallow gaming — let the assert be classified normally.
    asserts_outside = [
        a
        for a in ast.walk(func)
        if isinstance(a, ast.Assert) and not _node_inside_any(a, tries_with_pass_only)
    ]
    return not asserts_outside


def _handler_only_passes(handler: ast.ExceptHandler) -> bool:
    """True when `except: pass` (or with only a docstring + pass)."""
    body = [s for s in handler.body if not _is_docstring_stmt(s)]
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def _node_inside_any(target: ast.AST, parents: list[ast.AST]) -> bool:
    """True when `target` is a descendant of any node in `parents`."""
    for parent in parents:
        for child in ast.walk(parent):
            if child is target:
                return True
    return False


def _skipped_evidence(func: ast.FunctionDef) -> str:
    """`pytest.skip(...)` or `pytest.xfail(...)` at the top level of the body."""
    for stmt in func.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        callee = stmt.value.func
        if not isinstance(callee, ast.Attribute):
            continue
        if callee.attr in {"skip", "xfail"} and _attr_root_is(callee, "pytest"):
            return f"`pytest.{callee.attr}(...)` at top of test dodges the assertion"
    return ""


def _attr_root_is(attr: ast.Attribute, name: str) -> bool:
    """For `pytest.skip` → True if root attribute name is 'pytest'."""
    node: ast.expr = attr.value
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id == name


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
    return all(_node_inside_any(a, guards) for a in all_assertion_nodes)


def _monkeypatches_function_under_test(
    func: ast.FunctionDef, target_module: str, target_symbol: str
) -> bool:
    """True for `monkeypatch.setattr("<target_module>.<target_symbol>", ...)`.

    Also matches the 2-argument form `monkeypatch.setattr(<module>, "<symbol>",
    <stub>)` when the first arg is a `Name` referring to the imported module.
    """
    target_dotted = f"{target_module}.{target_symbol}"
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not _is_monkeypatch_setattr(node):
            continue
        if _setattr_first_arg_matches(node, target_dotted, target_module, target_symbol):
            return True
    return False


def _is_monkeypatch_setattr(node: ast.Call) -> bool:
    """True for `monkeypatch.setattr(...)` (any monkeypatch fixture name)."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "setattr":
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name) and "monkeypatch" in receiver.id.lower():
        return True
    return isinstance(receiver, ast.Attribute) and receiver.attr.lower() == "monkeypatch"


def _setattr_first_arg_matches(
    node: ast.Call, target_dotted: str, target_module: str, target_symbol: str
) -> bool:
    """Match `setattr("a.b.c", ...)` or `setattr(<module>, "symbol", ...)`."""
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and first.value == target_dotted:
        return True
    return (
        isinstance(first, ast.Name)
        and first.id == target_module.split(".")[-1]
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == target_symbol
    )


def _empty_body(func: ast.FunctionDef) -> bool:
    """Test body has no assertion and no pytest.raises.

    Allows the body to contain helper calls, comments, and a docstring;
    flags only when *no* assertion machinery is present at all.
    """
    has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(func))
    if has_assert:
        return False
    return not _has_raises_assertion(func)


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


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
