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
    """True when the body has a meaningful `assert <comparison>` outside the raises block.

    Excludes:
    - `assert True`/`assert False` (caught by python.tautological).
    - Asserts inside the `with pytest.raises(...):` block.
    - Metadata-only asserts: `inspect.signature(...)`, `callable(...)`,
      `hasattr(...)`, asserts on `.parameters`, `.__name__`, `.__module__`,
      `.__doc__`, `.__qualname__`. These are reflection over the symbol,
      not invocation — they don't validate behavior (BUG-035).
    - Constructor-input echo: `assert obj.attr == <literal>` where the
      literal value matches a kwarg passed when constructing `obj` in the
      same function. The test echoes its own input, validating nothing
      (BUG-033).
    """
    raises_call_ids = {id(c) for c in raises_calls}
    constructor_echoes = _collect_constructor_input_pairs(func)
    metadata_vars = _collect_metadata_assigned_vars(func)
    for node in ast.walk(func):
        if not isinstance(node, ast.Assert):
            continue
        if _assert_inside_raises(node, raises_call_ids, func):
            continue
        test = node.test
        if isinstance(test, ast.Constant):
            continue
        if _is_metadata_only(test, metadata_vars):
            continue
        if _is_constructor_input_echo(test, constructor_echoes):
            continue
        return True
    return False


_METADATA_ATTRS: frozenset[str] = frozenset(
    {"parameters", "__name__", "__module__", "__doc__", "__qualname__", "__class__", "__bases__"}
)
_METADATA_CALLS: frozenset[str] = frozenset(
    {"signature", "getsource", "getsourcelines", "getfullargspec", "getmembers"}
)
_METADATA_BUILTINS: frozenset[str] = frozenset(
    {"callable", "hasattr", "isinstance", "issubclass", "type", "id"}
)


def _is_metadata_only(node: ast.expr, metadata_vars: set[str]) -> bool:
    """True when `node` is an assertion shape that introspects the symbol rather
    than invoking it. These don't count as value assertions.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in _METADATA_ATTRS:
            return True
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Attribute) and fn.attr in _METADATA_CALLS:
                return True
            if isinstance(fn, ast.Name) and fn.id in _METADATA_BUILTINS:
                return True
        if isinstance(sub, ast.Name) and sub.id in metadata_vars:
            return True
    return False


def _collect_metadata_assigned_vars(func: ast.FunctionDef) -> set[str]:
    """Return names assigned from metadata calls (`sig = inspect.signature(...)`).

    Subsequent asserts on these vars (`assert sig.parameters[...] == ...`)
    are treated as metadata-only, not value assertions.
    """
    out: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        fn = node.value.func
        is_meta = (isinstance(fn, ast.Attribute) and fn.attr in _METADATA_CALLS) or (
            isinstance(fn, ast.Name) and fn.id in _METADATA_BUILTINS
        )
        if not is_meta:
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                out.add(tgt.id)
    return out


def _collect_constructor_input_pairs(func: ast.FunctionDef) -> dict[str, set]:
    """Return {var_name: {literal_value, ...}} for each `var = Cls(kw=literal, ...)`.

    The literals are the kwarg values used to construct `var`. Echo-asserts
    against these values are tautological — they re-assert the test's own input.
    """
    pairs: dict[str, set] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        var = node.targets[0].id
        for kw in node.value.keywords:
            if isinstance(kw.value, ast.Constant):
                pairs.setdefault(var, set()).add(kw.value.value)
        for arg in node.value.args:
            if isinstance(arg, ast.Constant):
                pairs.setdefault(var, set()).add(arg.value)
    return pairs


def _is_constructor_input_echo(node: ast.expr, pairs: dict[str, set]) -> bool:
    """True when node is `obj.attr == <literal>` and that literal was passed to
    construct `obj` in the same function body."""
    if not isinstance(node, ast.Compare) or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq):
        return False
    left, right = node.left, node.comparators[0]
    return _attr_matches_constructor(left, right, pairs) or _attr_matches_constructor(
        right, left, pairs
    )


def _attr_matches_constructor(side_a: ast.expr, side_b: ast.expr, pairs: dict[str, set]) -> bool:
    if not isinstance(side_a, ast.Attribute) or not isinstance(side_a.value, ast.Name):
        return False
    if not isinstance(side_b, ast.Constant):
        return False
    var = side_a.value.id
    return var in pairs and side_b.value in pairs[var]


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
