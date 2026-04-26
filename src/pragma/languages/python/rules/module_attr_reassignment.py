"""Rule: python.module_attr_reassignment — `<module>.<symbol> = <stub>` swaps the target."""

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
    if target_module is None or target_symbol is None:
        return None
    module_root = target_module.split(".")[-1]
    if _has_reassignment(func, tree, target_module, target_symbol):
        return Verdict(
            kind="python.module_attr_reassignment",
            evidence=(f"`{module_root}.{target_symbol} = ...` reassigns the production target"),
            test_name=test_name,
        )
    return None


def _has_reassignment(
    func: ast.FunctionDef, tree: ast.AST | None, target_module: str, symbol: str
) -> bool:
    """Walk the test function body + the enclosing module body for
    `<module_root>.<symbol> = <expr>` assignments.

    Matches both simple (`pricing.discount`) and dotted (`pricing.utils.discount`)
    module references by comparing the full dotted name of the target's value
    against `target_module`.
    """
    sources: list[ast.AST] = [func]
    if isinstance(tree, ast.Module):
        sources.extend(tree.body)
    for src in sources:
        for node in ast.walk(src):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                if target.attr != symbol:
                    continue
                target_value_name = _dotted_name(target.value)
                if target_value_name != target_module:
                    continue
                if _is_identity_assignment(target, node.value, target_module, symbol):
                    continue
                return True
    return False


def _dotted_name(node: ast.expr) -> str | None:
    """Return the dotted name string for a Name or chained Attribute node, or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        if prefix is None:
            return None
        return f"{prefix}.{node.attr}"
    return None


def _is_identity_assignment(
    target: ast.Attribute, value: ast.expr, target_module: str, symbol: str
) -> bool:
    """`pricing.discount = pricing.discount` (a no-op) is not gaming."""
    if not isinstance(value, ast.Attribute):
        return False
    if value.attr != symbol:
        return False
    return _dotted_name(value.value) == target_module
