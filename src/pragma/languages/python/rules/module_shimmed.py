"""Rule: python.module_shimmed — sys.modules[X] = stub replaces the production module."""

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
    tree: ast.AST | None = None,
    **_: object,
) -> Verdict | None:
    if tree is None or not isinstance(tree, ast.Module):
        return None
    evidence = _shim_evidence(tree, target_module)
    if evidence is None:
        return None
    return Verdict(
        kind="python.module_shimmed",
        evidence=evidence,
        test_name=test_name,
    )


def _shim_evidence(tree: ast.Module, target_module: str | None) -> str | None:
    """Return an evidence string if a top-level sys.modules shim is found.

    Flags when:
    - sys.modules["X"] = ... or sys.modules.setdefault("X", ...) or
      sys.modules.update({"X": ...}) where X matches target_module.
    - OR when target_module is None, a sys.modules[X] assignment exists at top
      level, AND types.ModuleType is used anywhere at the top level of the module
      (the ModuleType call may be in a separate statement).
    """
    shimmed = _top_level_shimmed_modules(tree)
    for mod_name, uses_module_type in shimmed:
        if target_module is not None and mod_name == target_module:
            return f'sys.modules["{mod_name}"] = stub replaces the production module'
        if target_module is None and (uses_module_type or _top_level_uses_module_type(tree)):
            # The value may be a variable reference — also check entire top level
            # for any types.ModuleType(...) call.
            return (
                f'sys.modules["{mod_name}"] = types.ModuleType(...) at top level'
                " replaces the production module"
            )
    return None


def _top_level_uses_module_type(tree: ast.Module) -> bool:
    """True when any top-level statement contains a types.ModuleType call."""
    for stmt in tree.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _is_module_type_call(node):
                return True
    return False


def _is_module_type_call(node: ast.Call) -> bool:
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "ModuleType"
        and isinstance(func.value, ast.Name)
        and func.value.id == "types"
    ):
        return True
    return isinstance(func, ast.Name) and func.id == "ModuleType"


def _top_level_shimmed_modules(tree: ast.Module) -> list[tuple[str, bool]]:
    """Walk top-level statements; return (module_name, uses_module_type) pairs.

    Detects:
    - sys.modules["X"] = <expr>
    - sys.modules.setdefault("X", <expr>)
    - sys.modules.update({"X": <expr>, ...})
    """
    results: list[tuple[str, bool]] = []
    for stmt in tree.body:
        # sys.modules["X"] = <expr>
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                mod_name = _subscript_sys_modules_key(target)
                if mod_name is not None:
                    uses_mt = _uses_module_type(stmt.value)
                    results.append((mod_name, uses_mt))
        # sys.modules.setdefault("X", <expr>) or sys.modules.update({...})
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            pairs = _sys_modules_call_pairs(call)
            results.extend(pairs)
    return results


def _subscript_sys_modules_key(node: ast.expr) -> str | None:
    """Return the string key if node is sys.modules["<key>"], else None."""
    if not isinstance(node, ast.Subscript):
        return None
    if not _is_sys_modules(node.value):
        return None
    slc = node.slice
    if isinstance(slc, ast.Constant) and isinstance(slc.value, str):
        return slc.value
    return None


def _is_sys_modules(node: ast.expr) -> bool:
    """True for `sys.modules`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _sys_modules_call_pairs(call: ast.Call) -> list[tuple[str, bool]]:
    """Detect setdefault and update call patterns on sys.modules."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return []
    if not _is_sys_modules(func.value):
        return []

    if func.attr == "setdefault" and (
        call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)
    ):
        # sys.modules.setdefault("X", <expr>)
        mod_name = call.args[0].value
        value = call.args[1] if len(call.args) > 1 else None
        uses_mt = _uses_module_type(value) if value is not None else False
        return [(mod_name, uses_mt)]

    if func.attr == "update":
        # sys.modules.update({"X": <expr>, ...})
        results: list[tuple[str, bool]] = []
        if call.args and isinstance(call.args[0], ast.Dict):
            d = call.args[0]
            for key, val in zip(d.keys, d.values, strict=False):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    results.append((key.value, _uses_module_type(val)))
        return results

    return []


def _uses_module_type(node: ast.expr) -> bool:
    """True when the expression tree contains a types.ModuleType(...) call."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _is_module_type_call(child):
            return True
    return False
