"""Rule: python.stub_error_match — pytest.raises(NotImplementedError) on a stub.

Fires when every `pytest.raises(...)` in the body is shaped to match a stub's
"not implemented" contract — `pytest.raises(NotImplementedError)`,
`pytest.raises(..., match="not implemented")`, or `pytest.raises(Exception)` —
AND there's no other assertion validating real behavior.

Catches BUG-032: a positive-named test that asserts the production stub raises
`NotImplementedError`, ships green, and is the inverse of an honest test.
"""

from __future__ import annotations

import ast

from pragma.verdict import Verdict

# Same vocabulary as vitest. Substring match on the stripped lower-cased text.
_STUB_PHRASES: frozenset[str] = frozenset(
    {
        "not implemented",
        "unimplemented",
        "not yet implemented",
        "todo",
        "tbd",
        "fixme",
        "stub",
        "no-op",
        "noop",
        "placeholder",
        "not connected",
        "offline",
        "not configured",
        "backend down",
        "service unavailable",
        "no api key",
        "not initialized",
    }
)

# Exception classes that match the stub's "raise NotImplementedError(...)" or
# bare `raise Exception(...)`. The stub-shape signal is a class that's so
# generic it accepts any "not done" error.
_STUB_EXCEPTION_NAMES: frozenset[str] = frozenset(
    {"NotImplementedError", "Exception", "BaseException"}
)


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    **_: object,
) -> Verdict | None:
    raises_calls = list(_collect_pytest_raises(func))
    if not raises_calls:
        return None

    if not all(_is_stub_shaped(call) for call in raises_calls):
        return None

    if _has_value_assertion(func, raises_calls):
        return None

    return Verdict(
        kind="python.stub_error_match",
        evidence=(
            "test's only pytest.raises shapes match the stub's contract "
            "(NotImplementedError, Exception, or match='not implemented') "
            "and no assert validates real behavior — pins the stub's "
            "'not yet implemented' contract, not validated behavior"
        ),
        test_name=test_name,
    )


def _collect_pytest_raises(func: ast.FunctionDef) -> list[ast.Call]:
    """Return every `pytest.raises(...)` Call expression in the body."""
    out: list[ast.Call] = []
    for node in ast.walk(func):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if (
                    isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Attribute)
                    and expr.func.attr == "raises"
                ):
                    out.append(expr)
    return out


def _is_stub_shaped(call: ast.Call) -> bool:
    """Return True when this `pytest.raises(...)` call matches a stub's contract."""
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Name) and first.id in _STUB_EXCEPTION_NAMES:
            return True
        if isinstance(first, ast.Attribute) and first.attr in _STUB_EXCEPTION_NAMES:
            return True

    for kw in call.keywords:
        if kw.arg == "match" and isinstance(kw.value, ast.Constant):
            text = str(kw.value.value).lower()
            if any(phrase in text for phrase in _STUB_PHRASES):
                return True

    return False


def _has_value_assertion(func: ast.FunctionDef, raises_calls: list[ast.Call]) -> bool:
    """True when the body has an `assert <comparison/value>` outside the raises block.

    We exclude `assert True`/`assert False` since those are themselves gaming
    patterns caught by python.tautological.
    """
    raises_call_ids = {id(c) for c in raises_calls}
    for node in ast.walk(func):
        if not isinstance(node, ast.Assert):
            continue
        if _assert_inside_raises(node, raises_call_ids, func):
            continue
        test = node.test
        if isinstance(test, ast.Constant):
            continue
        return True
    return False


def _assert_inside_raises(
    assert_node: ast.Assert,
    raises_call_ids: set[int],
    func: ast.FunctionDef,
) -> bool:
    """True when this assert sits inside a `with pytest.raises(...):` block."""
    for node in ast.walk(func):
        if not isinstance(node, ast.With):
            continue
        if not any(
            isinstance(item.context_expr, ast.Call) and id(item.context_expr) in raises_call_ids
            for item in node.items
        ):
            continue
        for child in ast.walk(node):
            if child is assert_node:
                return True
    return False
