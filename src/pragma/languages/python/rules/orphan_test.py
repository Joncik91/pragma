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
    orphan_local_defs: frozenset[str] | None = None,
    orphan_imports_target: bool | None = None,
    **_: object,
) -> Verdict | None:
    if tree is None or file_path is None:
        return None
    module_name = _module_name_from_basename(file_path.name)
    if module_name is None:
        return None
    # Whether the file imports its same-named target is a file-level fact; the
    # orchestrator precomputes it once (Fix 2) — a full-module walk per test was
    # the dominant O(n^2) cost. Fall back for callers that don't supply it.
    imports_target = (
        orphan_imports_target
        if orphan_imports_target is not None
        else _imports_target(tree, module_name)
    )
    if imports_target:
        return None
    pascal = _to_pascal(module_name)
    # `orphan_local_defs` is the file-level set of locally-defined class names
    # (PascalCase) and function names (snake_case) keyed `Class:<name>` /
    # `func:<name>`; the orchestrator precomputes it once (Fix 2). Fall back to
    # a per-call module scan for callers that don't supply it.
    local_defs = orphan_local_defs if orphan_local_defs is not None else _local_def_names(tree)
    if not _func_references_named(func, pascal, module_name, local_defs):
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


def _local_def_names(tree: ast.AST) -> frozenset[str]:
    """Module-level definitions as a file-level fact, tagged by kind:
    `Class:<name>` for ClassDef, `func:<name>` for FunctionDef.

    Used to require that an orphan reference resolves to a locally-defined
    (not imported) class or function, avoiding false positives on bare names.
    """
    if not isinstance(tree, ast.Module):
        return frozenset()
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            names.add(f"Class:{stmt.name}")
        elif isinstance(stmt, ast.FunctionDef):
            names.add(f"func:{stmt.name}")
    return frozenset(names)


def _func_references_named(
    func: ast.FunctionDef,
    pascal: str,
    snake: str,
    local_defs: frozenset[str],
) -> bool:
    """True if the test body references a same-named local class/function.

    Checks:
    1. The function body contains a ``Name(id=pascal)`` reference (constructor call).
    2. The function body contains a ``Name(id=snake)`` reference (function call).
    3. The module locally defines ``class <pascal>`` or ``def <snake>``.
    """
    func_has_pascal_ref = any(
        isinstance(node, ast.Name) and node.id == pascal for node in ast.walk(func)
    )
    func_has_snake_ref = any(
        isinstance(node, ast.Name) and node.id == snake for node in ast.walk(func)
    )
    if not (func_has_pascal_ref or func_has_snake_ref):
        return False
    return f"Class:{pascal}" in local_defs or f"func:{snake}" in local_defs
