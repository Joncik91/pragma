"""Python language plugin for Pragma.

Conforms to `pragma.languages._protocol.Classifier`. Exports:
- LANGUAGE: the prefix used in verdict kinds.
- matches(path): True when `path` is a Python test file we should classify.
- classify_file(path): list of Verdict, one per `test_*` function.
"""

from __future__ import annotations

import ast
from pathlib import Path

from pragma.languages.python.inference import infer_expected, infer_target
from pragma.languages.python.parser import walk_test_functions
from pragma.languages.python.rules import RULES
from pragma.verdict import Verdict

LANGUAGE = "python"


def matches(path: Path) -> bool:
    """True when path looks like a Python test file (extension-only)."""
    if path.suffix != ".py":
        return False
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py") or "tests" in path.resolve().parts


def classify_file(path: Path) -> list[Verdict]:
    """Classify every `test_*` function in `path`."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return [_classify_one(source, tree, func.name) for func in walk_test_functions(tree)]


def _classify_one(source: str, tree: ast.AST, test_name: str) -> Verdict:
    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == test_name),
        None,
    )
    assert func is not None  # walk_test_functions just gave it to us
    expected = infer_expected(test_name)
    target_module, target_symbol = infer_target(source, test_name)
    ctx = {
        "test_name": test_name,
        "expected": expected,
        "target_module": target_module,
        "target_symbol": target_symbol,
    }
    for rule in RULES:
        verdict = rule(func, **ctx)
        if verdict is not None:
            return verdict
    # Should never happen if the verified_fallback rule (6k) is registered.
    return Verdict(
        kind="python.verified",
        evidence="no rule matched (fallback)",
        test_name=test_name,
    )
