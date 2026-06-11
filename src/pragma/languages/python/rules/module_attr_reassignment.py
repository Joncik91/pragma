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
    module_reassignments: frozenset[tuple[str, str]] | None = None,
    **_: object,
) -> Verdict | None:
    if target_module is None or target_symbol is None:
        return None
    module_root = target_module.split(".")[-1]
    # The module-level reassignment scan is a file-level fact; the orchestrator
    # precomputes it once (Fix 2) and threads it in. The per-test body still
    # needs its own walk. Fall back to the full scan when not supplied.
    if module_reassignments is None:
        module_reassignments = (
            _collect_reassignments(tree.body) if isinstance(tree, ast.Module) else frozenset()
        )
    if (target_module, target_symbol) in module_reassignments or _func_has_reassignment(
        func, target_module, target_symbol
    ):
        return Verdict(
            kind="python.module_attr_reassignment",
            evidence=(f"`{module_root}.{target_symbol} = ...` reassigns the production target"),
            test_name=test_name,
        )
    return None


def _func_has_reassignment(func: ast.FunctionDef, target_module: str, symbol: str) -> bool:
    """True when the test body has a `<target_module>.<symbol> = <expr>`
    assignment (non-identity)."""
    return any(_is_target_reassignment(node, target_module, symbol) for node in ast.walk(func))


def _collect_reassignments(stmts: list[ast.stmt]) -> frozenset[tuple[str, str]]:
    """Module-level `<module>.<symbol> = <expr>` reassignments (non-identity),
    as a file-level fact keyed by `(module, symbol)`.

    Matches both simple (`pricing.discount`) and dotted (`pricing.utils.discount`)
    module references via the target value's full dotted name.
    """
    out: set[tuple[str, str]] = set()
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                module_name = _dotted_name(target.value)
                if module_name is None:
                    continue
                if _is_identity_assignment(target, node.value, module_name, target.attr):
                    continue
                out.add((module_name, target.attr))
    return frozenset(out)


def _is_target_reassignment(node: ast.AST, target_module: str, symbol: str) -> bool:
    if not isinstance(node, ast.Assign):
        return False
    for target in node.targets:
        if not isinstance(target, ast.Attribute):
            continue
        if target.attr != symbol:
            continue
        if _dotted_name(target.value) != target_module:
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
