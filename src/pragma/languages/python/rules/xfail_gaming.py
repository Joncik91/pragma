"""Rule: python.xfail_gaming — pytest.mark.xfail hides stub gaming.

Detects three forms:

1. Per-function decorator: `@pytest.mark.xfail(strict=True)` or
   `@pytest.mark.xfail(raises=NotImplementedError)` (with or without strict).
   Either form keeps CI green against an unimplemented stub.

2. Module-level: `pytestmark = pytest.mark.xfail(strict=True)` at the top of
   the file. Same gaming, harder to spot.

3. Decorator-via-variable: `stub_xfail = pytest.mark.xfail(...)` then
   `@stub_xfail` on each test. Pragma resolves the variable to its xfail
   binding before checking.
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
    name_to_xfail: dict[str, ast.Call] = _collect_xfail_bindings(tree) if tree is not None else {}

    evidence = _xfail_decorator_evidence(func, name_to_xfail)
    if evidence is None and tree is not None:
        evidence = _module_pytestmark_xfail_evidence(tree, name_to_xfail)
    if evidence is None:
        return None
    return Verdict(
        kind="python.xfail_gaming",
        evidence=evidence,
        test_name=test_name,
    )


def _xfail_decorator_evidence(
    func: ast.FunctionDef, name_to_xfail: dict[str, ast.Call]
) -> str | None:
    """Per-function decorator scan. Resolves decorator-via-variable."""
    for dec in func.decorator_list:
        call = _resolve_xfail_call(dec, name_to_xfail)
        if call is None:
            continue
        if _is_stub_pinning_xfail(call):
            return _evidence_for(call, source="decorator")
    return None


def _module_pytestmark_xfail_evidence(
    tree: ast.AST, name_to_xfail: dict[str, ast.Call]
) -> str | None:
    """Module-level pytestmark = pytest.mark.xfail(...) (or list containing one)."""
    if not isinstance(tree, ast.Module):
        return None
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not _assigns_to_pytestmark(stmt.targets):
            continue
        call = _value_xfail_call(stmt.value, name_to_xfail)
        if call is None:
            continue
        if _is_stub_pinning_xfail(call):
            return _evidence_for(call, source="pytestmark")
    return None


def _resolve_xfail_call(dec: ast.expr, name_to_xfail: dict[str, ast.Call]) -> ast.Call | None:
    """Return the underlying xfail Call, whether dec is a direct call or a name."""
    if isinstance(dec, ast.Call) and _is_xfail_callee(dec.func):
        return dec
    if isinstance(dec, ast.Name) and dec.id in name_to_xfail:
        return name_to_xfail[dec.id]
    return None


def _value_xfail_call(value: ast.expr, name_to_xfail: dict[str, ast.Call]) -> ast.Call | None:
    """Same as _resolve_xfail_call but also walks list/tuple values."""
    if isinstance(value, ast.Call) and _is_xfail_callee(value.func):
        return value
    if isinstance(value, ast.Name) and value.id in name_to_xfail:
        return name_to_xfail[value.id]
    if isinstance(value, ast.List | ast.Tuple):
        for elt in value.elts:
            call = _value_xfail_call(elt, name_to_xfail)
            if call is not None:
                return call
    return None


def _collect_xfail_bindings(tree: ast.AST) -> dict[str, ast.Call]:
    """Return {name: xfail_call} for module-level `name = pytest.mark.xfail(...)`."""
    out: dict[str, ast.Call] = {}
    if not isinstance(tree, ast.Module):
        return out
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        if not _is_xfail_callee(stmt.value.func):
            continue
        for tgt in stmt.targets:
            if isinstance(tgt, ast.Name) and tgt.id != "pytestmark":
                out[tgt.id] = stmt.value
    return out


def _is_stub_pinning_xfail(call: ast.Call) -> bool:
    """True when this xfail call is shaped to pin a stub.

    Two sufficient signals:
    - `strict=True` (any raises) — caught the original SWE-bench pattern.
    - `raises=NotImplementedError` (regardless of strict) — the giveaway that
      the test is pinning the stub, not a real-world failure mode.
    """
    if _has_strict_true(call):
        return True
    return _has_raises_not_implemented(call)


def _has_strict_true(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _has_raises_not_implemented(call: ast.Call) -> bool:
    """True if the xfail call carries raises=NotImplementedError (or Exception)."""
    targets = {"NotImplementedError", "Exception", "BaseException"}
    for kw in call.keywords:
        if kw.arg != "raises":
            continue
        v = kw.value
        if isinstance(v, ast.Name) and v.id in targets:
            return True
        if isinstance(v, ast.Attribute) and v.attr in targets:
            return True
    return False


def _assigns_to_pytestmark(targets: list[ast.expr]) -> bool:
    return any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets)


def _is_xfail_callee(callee: ast.expr) -> bool:
    """Match `pytest.mark.xfail` / `mark.xfail` / `xfail`."""
    if isinstance(callee, ast.Attribute) and callee.attr == "xfail":
        return True
    return isinstance(callee, ast.Name) and callee.id == "xfail"


def _evidence_for(call: ast.Call, *, source: str) -> str:
    """Return a human-readable evidence string for the given xfail call shape."""
    if _has_strict_true(call):
        prefix = "pytest.mark.xfail(strict=True)"
    elif _has_raises_not_implemented(call):
        prefix = "pytest.mark.xfail(raises=NotImplementedError)"
    else:
        prefix = "pytest.mark.xfail(...)"
    if source == "pytestmark":
        return (
            f"module-level pytestmark = {prefix} propagates to every test "
            "in the module — pins the stub's contract, keeps CI green"
        )
    return f"@{prefix} on a stub pins the stub's contract and keeps CI green"
