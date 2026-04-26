"""Rule: python.orphan_test — test_<name>.py never imports <name>; uses local fakes."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from pragma.verdict import Verdict

_BASENAME_RE = re.compile(r"^test_(?P<name>[a-z][a-z0-9_]*)\.py$")


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    tree: ast.AST | None = None,
    file_path: Path | None = None,
    **_: object,
) -> Verdict | None:
    if tree is None or file_path is None:
        return None
    module_name = _module_name_from_basename(file_path.name)
    if module_name is None:
        return None
    if _imports_target(tree, module_name):
        return None
    pascal = _to_pascal(module_name)
    if not _func_defines_or_calls_named(func, tree, pascal, module_name):
        return None
    return Verdict(
        kind="python.orphan_test",
        evidence=(
            f"test_{module_name}.py never imports {module_name!r}; "
            f"uses local {pascal} or {module_name}() instead"
        ),
        test_name=test_name,
    )


def _module_name_from_basename(name: str) -> str | None:
    """Extract <name> from 'test_<name>.py', or None if no match."""
    m = _BASENAME_RE.match(name)
    return m.group("name") if m else None


def _imports_target(tree: ast.AST, name: str) -> bool:
    """True if the module imports `name` anywhere (top-level or in functions).

    Catches:
    - ``import <name>``
    - ``import <pkg>.<name>``
    - ``from <name> import ...``
    - ``from <pkg>.<name> import ...``
    - ``from <pkg> import <name>``
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # import name  OR  import pkg.name
                parts = alias.name.split(".")
                if parts[-1] == name or alias.name == name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            parts = module.split(".")
            # from name import ...  OR  from pkg.name import ...
            if parts[-1] == name or module == name:
                return True
            # from pkg import name
            for alias in node.names:
                if alias.name == name:
                    return True
    return False


def _to_pascal(snake: str) -> str:
    """Convert snake_case to PascalCase. 'user_repo' → 'UserRepo'."""
    return "".join(seg.title() for seg in snake.split("_"))


def _func_defines_or_calls_named(
    func: ast.FunctionDef,
    tree: ast.AST,
    pascal: str,
    snake: str,
) -> bool:
    """True if the test function body references a same-named local class or function.

    Checks:
    1. The function body contains a ``Name(id=pascal)`` reference (constructor call).
    2. The function body contains a ``Name(id=snake)`` reference (function call).
    3. The module body defines a ``ClassDef(name=pascal)`` or ``FunctionDef(name=snake)``
       locally (not imported).
    """
    # Check for name reference inside the function body
    func_has_pascal_ref = any(
        isinstance(node, ast.Name) and node.id == pascal for node in ast.walk(func)
    )
    func_has_snake_ref = any(
        isinstance(node, ast.Name) and node.id == snake for node in ast.walk(func)
    )
    if not (func_has_pascal_ref or func_has_snake_ref):
        return False

    # Require that there's a local definition of that class/function in the module
    # (not imported) — to avoid false positives on mere string literals or unrelated names.
    if isinstance(tree, ast.Module):
        for stmt in tree.body:
            if isinstance(stmt, ast.ClassDef) and stmt.name == pascal:
                return True
            if isinstance(stmt, ast.FunctionDef) and stmt.name == snake:
                return True
    return False
