"""Rule: python.mocked-away — test patches the function under test."""

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
    **_: object,
) -> Verdict | None:
    if target_module is None or target_symbol is None:
        return None
    if _mocks_function_under_test(func, target_module, target_symbol):
        return Verdict(
            kind="python.mocked-away",
            evidence=f"mock.patch on {target_module}.{target_symbol} (the function under test)",
            test_name=test_name,
        )
    return None


def _mocks_function_under_test(
    func: ast.FunctionDef,
    target_module: str,
    target_symbol: str,
) -> bool:
    """True when the test patches the production target."""
    target = f"{target_module}.{target_symbol}"
    if any(_is_patch_with_target(n, target) for n in ast.walk(func)):
        return True
    return any(_is_patch_with_target(d, target) for d in func.decorator_list)


def _is_patch_with_target(node: ast.AST, target: str) -> bool:
    if not isinstance(node, ast.Call) or not _is_patch_call(node):
        return False
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return False
    return node.args[0].value == target


def _is_patch_call(node: ast.Call) -> bool:
    """True for `patch(...)` / `mock.patch(...)` / `unittest.mock.patch(...)`."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "patch":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "patch"
