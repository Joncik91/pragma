"""Heuristic inference of classifier inputs from a test's source.

The classifier in `test_gaming.py` needs `expected` (success/reject) and
optionally a target `(module, symbol)` to detect mocked-away. The watcher
ships with **zero config**, so both are inferred:

- `expected` — derived from the test name. Names that contain `_rejects_`,
  `_raises_`, `_refuses_`, or `_denies_` map to `"reject"`. Everything
  else maps to `"success"`.
- `(module, symbol)` — derived from the test body. We walk the test's
  `from <module> import <symbol>` lines, filter out stdlib + test-only
  modules, and pick the most-recently-imported non-test symbol that the
  test body actually `Call`s. Returns `(None, None)` when nothing
  qualifies; the classifier then skips the mocked-away check.
"""

from __future__ import annotations

import ast
import re

_REJECT_PATTERN = re.compile(r"_(?:rejects?|raises?|refuses?|denies)_")

# Modules whose imports are never the production target. Hard-coded
# because requiring the user to configure this defeats the "zero
# config" promise. Add to this list rather than inventing config.
_STDLIB_PREFIXES: frozenset[str] = frozenset(
    {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "concurrent",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "random",
        "re",
        "secrets",
        "shutil",
        "socket",
        "sqlite3",
        "stat",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "zipfile",
    }
)

# Modules that *aren't* stdlib but are never production code under test.
_TEST_ONLY_PREFIXES: frozenset[str] = frozenset({"pytest", "mock"})


def infer_expected(test_name: str) -> str:
    """Map test name to `"success"` or `"reject"`."""
    if _REJECT_PATTERN.search(test_name):
        return "reject"
    return "success"


def infer_target(source: str, test_name: str) -> tuple[str | None, str | None]:
    """Pick (module, symbol) the test exercises, or (None, None) if unclear."""
    tree = ast.parse(source)
    func = _find_test_func(tree, test_name)
    if func is None:
        return None, None
    imports = _collect_module_level_imports(tree) + _collect_imports_in(func)
    if not imports:
        return None, None
    called = _called_names(func)
    # Walk imports in *reverse* so the most-recently-declared one wins.
    for module, symbol in reversed(imports):
        if symbol in called:
            return module, symbol
    return None, None


def _find_test_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _collect_module_level_imports(tree: ast.AST) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            pairs.extend(_pairs_from_importfrom(node))
    return pairs


def _collect_imports_in(func: ast.FunctionDef) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.ImportFrom):
            pairs.extend(_pairs_from_importfrom(node))
    return pairs


def _pairs_from_importfrom(node: ast.ImportFrom) -> list[tuple[str, str]]:
    module = node.module or ""
    if not module or _is_excluded_module(module):
        return []
    return [(module, alias.name) for alias in node.names if alias.name != "*"]


def _is_excluded_module(module: str) -> bool:
    """True if `module` is stdlib, a test-only library, or a tests/* package."""
    head = module.split(".", 1)[0]
    if head in _STDLIB_PREFIXES or head in _TEST_ONLY_PREFIXES:
        return True
    return module.startswith("tests") or head.startswith("test_")


def _called_names(func: ast.FunctionDef) -> set[str]:
    """Names that appear as the callee of a `Call` node in the body."""
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = _callee_name(node.func)
            if name:
                names.add(name)
    return names


def _callee_name(expr: ast.expr) -> str | None:
    """Resolve a Call's func to a bare name, or None if it isn't a name."""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None
