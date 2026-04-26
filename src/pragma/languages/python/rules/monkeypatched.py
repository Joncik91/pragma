"""Rule: python.monkeypatched — test uses monkeypatch.setattr on the function under test."""

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
    if _monkeypatches_function_under_test(func, target_module, target_symbol):
        return Verdict(
            kind="python.monkeypatched",
            evidence=(
                f"monkeypatch.setattr on {target_module}.{target_symbol} (the function under test)"
            ),
            test_name=test_name,
        )
    return None


def _monkeypatches_function_under_test(
    func: ast.FunctionDef, target_module: str, target_symbol: str
) -> bool:
    """True for `monkeypatch.setattr("<target_module>.<target_symbol>", ...)`.

    Also matches the 2-argument form `monkeypatch.setattr(<module>, "<symbol>",
    <stub>)` when the first arg is a `Name` referring to the imported module.
    """
    target_dotted = f"{target_module}.{target_symbol}"
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not _is_monkeypatch_setattr(node):
            continue
        if _setattr_first_arg_matches(node, target_dotted, target_module, target_symbol):
            return True
    return False


def _is_monkeypatch_setattr(node: ast.Call) -> bool:
    """True for `monkeypatch.setattr(...)` (any monkeypatch fixture name)."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "setattr":
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name) and "monkeypatch" in receiver.id.lower():
        return True
    return isinstance(receiver, ast.Attribute) and receiver.attr.lower() == "monkeypatch"


def _setattr_first_arg_matches(
    node: ast.Call, target_dotted: str, target_module: str, target_symbol: str
) -> bool:
    """Match `setattr("a.b.c", ...)` or `setattr(<module>, "symbol", ...)`."""
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and first.value == target_dotted:
        return True
    return (
        isinstance(first, ast.Name)
        and first.id == target_module.split(".")[-1]
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == target_symbol
    )
