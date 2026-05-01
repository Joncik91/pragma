"""Rule: python.skipped — pytest.skip / xfail dodges the assertion.

Detects three forms:
1. Top-of-body call: `pytest.skip(...)` or `pytest.xfail(...)`.
2. `try: stub_call(); except NotImplementedError: pytest.skip(...)` — convert
   the stub's raise into a clean skip. Same gaming, hidden in an except clause.
3. Helper-via-name: `try: ...; except NotImplementedError as exc: _skip_if_stub(exc)`
   where `_skip_if_stub` is defined in the same file and calls `pytest.skip`.
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
    skip_helpers = _collect_skip_helper_names(tree) if tree is not None else set()
    evidence = _skipped_evidence(func, skip_helpers)
    if evidence:
        return Verdict(kind="python.skipped", evidence=evidence, test_name=test_name)
    return None


def _skipped_evidence(func: ast.FunctionDef, skip_helpers: set[str]) -> str:
    """Return evidence text when any skip-pattern is detected in the body."""
    for stmt in func.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        callee = stmt.value.func
        if not isinstance(callee, ast.Attribute):
            continue
        if callee.attr in {"skip", "xfail"} and _attr_root_is(callee, "pytest"):
            return f"`pytest.{callee.attr}(...)` at top of test dodges the assertion"

    for node in ast.walk(func):
        if isinstance(node, ast.Try):
            evidence = _try_handler_skip_evidence(node, skip_helpers)
            if evidence:
                return evidence
    return ""


def _try_handler_skip_evidence(try_node: ast.Try, skip_helpers: set[str]) -> str:
    """Inspect each except clause for a pytest.skip path that dodges the stub.

    Two flavours we flag:
    - `except NotImplementedError: pytest.skip(...)` (or .xfail).
    - `except NotImplementedError: _skip_helper(...)` where the helper calls skip.
    """
    for handler in try_node.handlers:
        if not _handler_matches_stub_exception(handler):
            continue
        for sub in ast.walk(handler):
            if not isinstance(sub, ast.Call):
                continue
            if _is_pytest_skip_or_xfail_call(sub.func):
                return (
                    "try/except NotImplementedError → pytest.skip dodges the stub: "
                    "the test silently skips whenever the production stub raises, "
                    "so CI stays green forever"
                )
            if isinstance(sub.func, ast.Name) and sub.func.id in skip_helpers:
                return (
                    f"try/except NotImplementedError → {sub.func.id}(...) helper "
                    "that calls pytest.skip dodges the stub: CI stays green forever"
                )
    return ""


def _handler_matches_stub_exception(handler: ast.ExceptHandler) -> bool:
    """True when the handler catches NotImplementedError or a generic Exception."""
    targets = {"NotImplementedError", "Exception", "BaseException"}
    exc = handler.type
    if exc is None:
        # bare `except:` — same effect.
        return True
    if isinstance(exc, ast.Name) and exc.id in targets:
        return True
    if isinstance(exc, ast.Attribute) and exc.attr in targets:
        return True
    if isinstance(exc, ast.Tuple):
        return any(
            (isinstance(e, ast.Name) and e.id in targets)
            or (isinstance(e, ast.Attribute) and e.attr in targets)
            for e in exc.elts
        )
    return False


def _is_pytest_skip_or_xfail_call(callee: ast.expr) -> bool:
    if isinstance(callee, ast.Attribute) and callee.attr in {"skip", "xfail"}:
        return _attr_root_is(callee, "pytest")
    return False


def _collect_skip_helper_names(tree: ast.AST) -> set[str]:
    """Return module-level function names whose body calls pytest.skip / xfail.

    Catches the helper-via-name pattern (`_skip_if_stub(exc)` that calls skip).
    """
    out: set[str] = set()
    if not isinstance(tree, ast.Module):
        return out
    for stmt in tree.body:
        if not isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call) and _is_pytest_skip_or_xfail_call(sub.func):
                out.add(stmt.name)
                break
    return out


def _attr_root_is(attr: ast.Attribute, name: str) -> bool:
    """For `pytest.skip` → True if root attribute name is 'pytest'."""
    node: ast.expr = attr.value
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id == name
