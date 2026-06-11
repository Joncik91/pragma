"""Rule: python.conditional — every assertion lives inside a conditional branch."""

from __future__ import annotations

import ast

from pragma.languages.python.rules._shared import _is_with_raises, node_inside_any
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
    if _all_assertions_conditional(func):
        return Verdict(
            kind="python.conditional",
            evidence="all assertions live inside conditional branches the inputs never enter",
            test_name=test_name,
        )
    return None


def _all_assertions_conditional(func: ast.FunctionDef) -> bool:
    """True when every assertion (and pytest.raises with-block) is nested
    inside an `if`/`for`/`while` that the inputs may never enter. Indicates
    the assertions may never run.

    Conservative: requires at least one assertion AND every one to be
    nested. A test with one top-level assert + one conditional assert is
    not flagged.

    Exempt guards (Fix 1b) are NOT counted as dead branches:
    - `for ... in <inline literal table>` — the loop body runs once per row.
    - recognized platform/env guards (`sys.platform`, `os.environ`) — the
      branch runs on the matching platform.
    An assertion that lives only inside exempt guards is treated as if it
    runs unconditionally, so the test is clean.
    """
    asserts = [a for a in ast.walk(func) if isinstance(a, ast.Assert)]
    raises_withs = [n for n in ast.walk(func) if isinstance(n, ast.With) and _is_with_raises(n)]
    all_assertion_nodes = asserts + raises_withs
    if not all_assertion_nodes:
        return False
    guards = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.If | ast.For | ast.While) and not _is_exempt_guard(n)
    ]
    if not guards:
        return False
    return all(node_inside_any(a, guards) for a in all_assertion_nodes)


def _is_exempt_guard(node: ast.AST) -> bool:
    """A guard whose body genuinely executes: a literal-table `for`-loop or a
    recognized platform/environment guard."""
    if isinstance(node, ast.For):
        return _iterates_literal_table(node)
    if isinstance(node, ast.If):
        return _is_platform_or_env_guard(node.test)
    return False


def _iterates_literal_table(node: ast.For) -> bool:
    """`for ... in [<rows>]` / `(<rows>,)` with at least one literal row."""
    it = node.iter
    return isinstance(it, ast.List | ast.Tuple) and len(it.elts) > 0


def _is_platform_or_env_guard(test: ast.expr) -> bool:
    """Recognize `sys.platform == ...`, `os.environ[...]`/`os.environ.get(...)`
    comparisons, and boolean combinations thereof."""
    if isinstance(test, ast.BoolOp):
        return any(_is_platform_or_env_guard(v) for v in test.values)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _is_platform_or_env_guard(test.operand)
    if isinstance(test, ast.Compare):
        return _references_platform_or_env(test.left) or any(
            _references_platform_or_env(c) for c in test.comparators
        )
    return _references_platform_or_env(test)


def _references_platform_or_env(node: ast.expr) -> bool:
    """True if `node` reads `sys.platform`, `os.name`, or `os.environ[...]`."""
    # `os.environ.get("X")` / `os.environ["X"]`
    if isinstance(node, ast.Call) and _references_platform_or_env(node.func):
        return True
    if isinstance(node, ast.Subscript):
        return _references_platform_or_env(node.value)
    if isinstance(node, ast.Attribute):
        target = node.value
        if isinstance(target, ast.Name) and target.id == "sys" and node.attr == "platform":
            return True
        if isinstance(target, ast.Name) and target.id == "os" and node.attr in {"environ", "name"}:
            return True
        # `os.environ.get` → recurse onto `os.environ`.
        return _references_platform_or_env(node.value)
    return False
