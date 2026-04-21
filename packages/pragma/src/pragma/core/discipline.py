from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_COMPLEXITY_BUDGET = 10
_LOC_PER_FUNCTION_BUDGET = 60
_LOC_PER_FILE_BUDGET = 400
_NESTING_DEPTH_BUDGET = 3
_TODO_MARKERS = ("TODO", "FIXME", "XXX")


@dataclass(frozen=True)
class DisciplineViolation:
    rule: str
    path: str
    line: int
    got: int
    budget: int
    remediation: str


def _build_subclass_map(tree: ast.AST) -> dict[str, list[str]]:
    subclass_map: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = _dec_name(base)
                if name:
                    subclass_map.setdefault(name, []).append(node.name)
    return subclass_map


def _walk_tree_violations(
    tree: ast.AST, path: str, subclass_map: dict[str, list[str]]
) -> list[DisciplineViolation]:
    violations: list[DisciplineViolation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            violations.extend(_check_function(node, path))
        elif isinstance(node, ast.ClassDef):
            violations.extend(_check_class(node, path, subclass_map))
    return violations


def _file_level_violations(source: str, path: str) -> list[DisciplineViolation]:
    if not source.strip():
        return []
    violations = list(_check_todo_sentinels(source, path))
    lines = source.splitlines()
    if len(lines) > _LOC_PER_FILE_BUDGET:
        violations.append(
            DisciplineViolation(
                rule="loc_per_file",
                path=path,
                line=1,
                got=len(lines),
                budget=_LOC_PER_FILE_BUDGET,
                remediation="Split this file into smaller modules.",
            )
        )
    return violations


def check_source(source: str, *, path: str) -> list[DisciplineViolation]:
    violations: list[DisciplineViolation] = list(_empty_init(source, path))
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [
            DisciplineViolation(
                rule="syntax_error",
                path=path,
                line=exc.lineno or 1,
                got=1,
                budget=0,
                remediation="Fix the syntax error before running discipline checks.",
            )
        ]
    subclass_map = _build_subclass_map(tree)
    violations.extend(_walk_tree_violations(tree, path, subclass_map))
    violations.extend(_file_level_violations(source, path))
    return violations


def check_file(path: Path) -> list[DisciplineViolation]:
    source = path.read_text(encoding="utf-8")
    return check_source(source, path=str(path))


def _check_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef, path: str
) -> list[DisciplineViolation]:
    violations: list[DisciplineViolation] = []
    cc = _cyclomatic(node)
    if cc > _COMPLEXITY_BUDGET:
        violations.append(
            DisciplineViolation(
                rule="complexity",
                path=path,
                line=node.lineno,
                got=cc,
                budget=_COMPLEXITY_BUDGET,
                remediation="Reduce cyclomatic complexity: extract helpers or use early returns.",
            )
        )
    loc = node.end_lineno - node.lineno + 1 if node.end_lineno else 1
    if loc > _LOC_PER_FUNCTION_BUDGET:
        violations.append(
            DisciplineViolation(
                rule="loc_per_function",
                path=path,
                line=node.lineno,
                got=loc,
                budget=_LOC_PER_FUNCTION_BUDGET,
                remediation="Break this function into smaller pieces.",
            )
        )
    nd = _max_nesting_depth(node)
    if nd > _NESTING_DEPTH_BUDGET:
        violations.append(
            DisciplineViolation(
                rule="nesting_depth",
                path=path,
                line=node.lineno,
                got=nd,
                budget=_NESTING_DEPTH_BUDGET,
                remediation="Flatten nesting with early returns or extract nested logic.",
            )
        )
    return violations


def _check_class(
    node: ast.ClassDef, path: str, subclass_map: dict[str, list[str]]
) -> list[DisciplineViolation]:
    violations: list[DisciplineViolation] = []
    if _is_single_method_util(node):
        violations.append(
            DisciplineViolation(
                rule="single_method_util",
                path=path,
                line=node.lineno,
                got=1,
                budget=0,
                remediation="Replace this utility class with a standalone function.",
            )
        )
    if node.name in subclass_map and len(subclass_map[node.name]) == 1:
        violations.append(
            DisciplineViolation(
                rule="single_subclass_base",
                path=path,
                line=node.lineno,
                got=1,
                budget=0,
                remediation="Remove the base class or add a second concrete subclass.",
            )
        )
    return violations


def _is_dataclass_or_pydantic(node: ast.ClassDef) -> bool:
    for deco in node.decorator_list:
        name = _dec_name(deco)
        if name in ("dataclass", "frozen_dataclass"):
            return True
    for base in node.bases:
        name = _dec_name(base)
        if name in ("BaseModel",):
            return True
    return False


def _dec_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _dec_name(node.func)
    return None


def _is_single_method_util(node: ast.ClassDef) -> bool:
    if _is_dataclass_or_pydantic(node):
        return False
    methods = [
        n
        for n in node.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name != "__init__"
    ]
    return len(methods) == 1 and len(node.body) <= 3


def _cyclomatic(node: ast.AST) -> int:
    count = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            ast.If
            | ast.For
            | ast.AsyncFor
            | ast.While
            | ast.ExceptHandler
            | ast.With
            | ast.AsyncWith
            | ast.Assert,
        ):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
        elif isinstance(child, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
            count += 1
    return count


def _max_nesting_depth(node: ast.AST) -> int:
    def _walk(n: ast.AST, depth: int) -> int:
        max_d = depth
        for child in ast.iter_child_nodes(n):
            if isinstance(
                child,
                ast.If | ast.For | ast.AsyncFor | ast.While | ast.With | ast.AsyncWith | ast.Try,
            ):
                max_d = max(max_d, _walk(child, depth + 1))
            else:
                max_d = max(max_d, _walk(child, depth))
        return max_d

    return _walk(node, 0)


def _check_todo_sentinels(source: str, path: str) -> list[DisciplineViolation]:
    violations: list[DisciplineViolation] = []
    for i, line in enumerate(source.splitlines(), start=1):
        for marker in _TODO_MARKERS:
            if re.search(rf"\b{marker}\b", line):
                violations.append(
                    DisciplineViolation(
                        rule="todo_sentinel",
                        path=path,
                        line=i,
                        got=1,
                        budget=0,
                        remediation=f"Resolve the {marker} marker before merging.",
                    )
                )
                break
    return violations


def _empty_init(source: str, path: str) -> list[DisciplineViolation]:
    if path.endswith("__init__.py") and not source.strip():
        return [
            DisciplineViolation(
                rule="empty_init",
                path=path,
                line=1,
                got=1,
                budget=0,
                remediation="Add a docstring or explicit re-exports to __init__.py.",
            )
        ]
    return []
