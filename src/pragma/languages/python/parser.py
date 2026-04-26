"""AST parsing helpers for Python test files.

`async def test_*` is treated identically to `def test_*` — `ast.AsyncFunctionDef`
shares the same `name`, `body`, `decorator_list`, and `args` shape as
`ast.FunctionDef`, so downstream rules can duck-type without union annotations.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

# Type alias documenting that downstream code accepts either.
_FuncNode = ast.FunctionDef | ast.AsyncFunctionDef


def find_test_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    """Return the FunctionDef (sync or async) matching `name`, or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node  # type: ignore[return-value]
    return None


def walk_test_functions(tree: ast.AST) -> Iterator[ast.FunctionDef]:
    """Yield every FunctionDef (sync or async) whose name starts with `test_`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            yield node  # type: ignore[misc]
