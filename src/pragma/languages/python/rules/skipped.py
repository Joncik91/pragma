"""Rule: python.skipped — pytest.skip / xfail at top of body dodges the assertion."""

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
    evidence = _skipped_evidence(func)
    if evidence:
        return Verdict(kind="python.skipped", evidence=evidence, test_name=test_name)
    return None


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
