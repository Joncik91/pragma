"""AST parsing helpers for Python test files."""

from __future__ import annotations

import ast
from collections.abc import Iterator


def find_test_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    """Return the FunctionDef matching `name`, or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def walk_test_functions(tree: ast.AST) -> Iterator[ast.FunctionDef]:
    """Yield every FunctionDef whose name starts with `test_`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            yield node
