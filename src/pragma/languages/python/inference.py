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

# The `raise(s)` token alone is a weak signal for an error-path expectation:
# a name like `test_button_raises_click_event` describes the *subject* under
# test (an event), not an exception. Reject inference driven *only* by this
# token must be corroborated by structure (pytest.raises / except) before it
# hard-blocks; otherwise it downgrades to a non-blocking warn. The other
# verbs (rejects/refuses/denies) are unambiguous and keep hard-blocking.
_RAISE_ONLY_PATTERN = re.compile(r"_raises?_")
_OTHER_REJECT_PATTERN = re.compile(r"_(?:rejects?|refuses?|denies)_")

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


def reject_is_raise_token_only(test_name: str) -> bool:
    """True when the only reason `test_name` infers `reject` is a `raise(s)`
    token (no `rejects/refuses/denies`). Such reject inference is uncorroborated
    by name alone and needs structural backing before it hard-blocks."""
    return bool(_RAISE_ONLY_PATTERN.search(test_name)) and not _OTHER_REJECT_PATTERN.search(
        test_name
    )


def infer_target(source: str, test_name: str) -> tuple[str | None, str | None]:
    """Pick (module, symbol) the test exercises, or (None, None) if unclear.

    Convenience wrapper that parses `source` itself. Hot callers that already
    hold a parsed tree should call `infer_target_in_tree` to avoid re-parsing
    the whole file once per test (the O(n^2) path — see Fix 2)."""
    return infer_target_in_tree(ast.parse(source), test_name)


def infer_target_in_tree(tree: ast.AST, test_name: str) -> tuple[str | None, str | None]:
    """Pick (module, symbol) the test exercises, given an already-parsed tree."""
    func = _find_test_func(tree, test_name)
    if func is None:
        return None, None
    return infer_target_for_func(tree, func)


def infer_target_for_func(tree: ast.AST, func: ast.FunctionDef) -> tuple[str | None, str | None]:
    """Same as `infer_target_in_tree` but the caller already holds `func`, so
    we skip the per-test `_find_test_func` walk. The hot path threads this in
    (Fix 2): finding the func via a full tree walk per test was the second
    O(n^2) factor on top of the per-test re-parse."""
    imports = _collect_module_level_imports(tree) + _collect_imports_in(func)
    called = _called_names(func)
    # Walk `from`-style imports in reverse so the most-recently-declared wins.
    for module, symbol in reversed(imports):
        if symbol in called:
            return module, symbol
    # Plain `import X` doesn't give us a (module, symbol) pair on its own.
    # Pair it with attribute access on the same name in the body:
    # `import tasks` + `tasks.schedule_task(...)` → ("tasks", "schedule_task").
    # Same shape covers `monkeypatch.setattr(tasks, "schedule_task", ...)`.
    plain = _collect_plain_module_imports(tree, func)
    if plain:
        for module in reversed(plain):
            symbol = _attr_used_on(func, module)
            if symbol is not None:
                return module, symbol
    return None, None


def _find_test_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node  # type: ignore[return-value]
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


def _collect_plain_module_imports(tree: ast.AST, func: ast.FunctionDef) -> list[str]:
    """Return module names from plain `import X` / `import X.Y` (not `from`).

    Skips stdlib and test-only modules so we don't claim those are the
    production target. Order is module-level-first, then in-function,
    mirroring `_collect_module_level_imports + _collect_imports_in`.
    """
    out: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            out.extend(_plain_modules_from(node))
    for node in ast.walk(func):
        if isinstance(node, ast.Import):
            out.extend(_plain_modules_from(node))
    return out


def _plain_modules_from(node: ast.Import) -> list[str]:
    return [alias.name for alias in node.names if not _is_excluded_module(alias.name)]


def _attr_used_on(func: ast.FunctionDef, module: str) -> str | None:
    """Return the attribute name when the test body uses `<module>.<attr>(...)`
    or `setattr(<module>, "<attr>", ...)`. Picks the first match seen.

    The bare module name (last segment of dotted path) is what appears
    as the receiver — `import auth.login` is bound as `auth` in the
    namespace, but real code does `auth.login.X`. Match the dotted root.
    """
    root = module.split(".", 1)[0]
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        # Attribute call: <root>.<attr>(...)
        if isinstance(node.func, ast.Attribute):
            sym = _attr_chain_symbol(node.func, module, root)
            if sym is not None:
                return sym
        # setattr-style: monkeypatch.setattr(<root>, "<attr>", ...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "setattr":
            sym = _setattr_symbol(node, root)
            if sym is not None:
                return sym
    return None


def _attr_chain_symbol(attr: ast.Attribute, module: str, root: str) -> str | None:
    """For `<root>.<x>.<y>(...)`, walk the chain and pick the attr that lives
    immediately under the module. Most calls are simple `<root>.<x>` so we
    return `<x>`; for `import a.b` + `a.b.foo(...)`, return `foo`."""
    chain: list[str] = []
    node: ast.expr = attr
    while isinstance(node, ast.Attribute):
        chain.insert(0, node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id != root:
        return None
    if module == root:
        return chain[0] if chain else None
    # `import a.b`, body uses `a.b.foo` → drop the dotted-suffix prefix.
    suffix = module.split(".")[1:]
    if chain[: len(suffix)] != suffix:
        return None
    rest = chain[len(suffix) :]
    return rest[0] if rest else None


def _setattr_symbol(node: ast.Call, root: str) -> str | None:
    """For `<owner>.setattr(<root>, "<attr>", <stub>)`, return `<attr>`."""
    if len(node.args) < 2:
        return None
    first, second = node.args[0], node.args[1]
    if not (isinstance(first, ast.Name) and first.id == root):
        return None
    if isinstance(second, ast.Constant) and isinstance(second.value, str):
        return second.value
    return None


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
