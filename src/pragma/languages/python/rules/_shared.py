"""AST predicates reused by multiple Python rule modules.

These helpers are the building blocks. Each rule file uses one or two
of them but never the others, so they live in their own module to keep
each rule single-purpose.
"""

from __future__ import annotations

import ast


def has_raises_assertion(func: ast.FunctionDef) -> bool:
    """True when the body uses `pytest.raises` (with-block) or `try/except`."""
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


def is_docstring_stmt(stmt: ast.stmt) -> bool:
    """True for a top-level docstring expression statement."""
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def has_real_value_assertion(func: ast.FunctionDef) -> bool:
    """True when the body has at least one assertion comparing against a
    concrete (non-None) expected value — `assert call(...) == <value>`,
    `assert x in y`, or `assert isinstance(x, T)`. Constant-only asserts
    (`assert True`, `assert x == x`) don't count; those are tautologies the
    dedicated rule handles. Used to decide whether an uncorroborated reject
    name is backed by a real return-value check."""
    for node in ast.walk(func):
        if isinstance(node, ast.Assert) and _is_concrete_value_assertion(node.test):
            return True
    return False


def _is_concrete_value_assertion(test: ast.expr) -> bool:
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op = test.ops[0]
        if isinstance(op, ast.Eq | ast.NotEq):
            return any(not _is_trivial_operand(c) for c in test.comparators)
        if isinstance(op, ast.In | ast.NotIn | ast.Lt | ast.LtE | ast.Gt | ast.GtE):
            return True
    return (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
    )


def _is_trivial_operand(node: ast.expr) -> bool:
    """A None constant or a bare-name echo that proves nothing on its own."""
    return isinstance(node, ast.Constant) and node.value is None


def node_inside_any(target: ast.AST, parents: list[ast.AST]) -> bool:
    """True when `target` is a descendant of any node in `parents`."""
    for parent in parents:
        for child in ast.walk(parent):
            if child is target:
                return True
    return False
