"""Python language plugin for Pragma.

Conforms to `pragma.languages._protocol.Classifier`. Exports:
- LANGUAGE: the prefix used in verdict kinds.
- matches(path): True when `path` is a Python test file we should classify.
- classify_file(path): list of Verdict, one per `test_*` function.
"""

from __future__ import annotations

import ast
from pathlib import Path

from pragma.languages.python.inference import infer_expected, infer_target_for_func
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
    """Classify every `test_*` function in `path`, then apply the file-level
    `no_success_assertion` pass over the resulting verdicts."""
    from pragma.languages.python.rules.no_success_assertion import apply_file_pass

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        # A file we cannot read/parse is not gamed — it's noise. Return one
        # explicit, non-blocking skip verdict instead of letting the exception
        # propagate (which would fail open: the caller would treat the crash as
        # "no verdicts" and silently pass the file). See Fix 3.
        return [
            Verdict(
                kind="python.unparseable",
                evidence=f"could not parse {path.name}: {type(exc).__name__}: {exc}",
                test_name=path.name,
            )
        ]
    # Parse once, thread the tree to every per-test pass. Re-parsing the whole
    # file per test (the old `infer_target(source, ...)` path) was O(n^2) in the
    # number of tests — 57.5s on a 1000-test file. See Fix 2.
    #
    # Several rules also need *file-level* facts (module-level skip helpers,
    # local class/func defs, module-level target reassignments). Computing them
    # per test was the other O(n^2) factor — each was a full-module walk. Hoist
    # them here and thread them into every per-test ctx.
    file_ctx = _build_file_ctx(tree, path)
    verdicts = [_classify_one(tree, func, path, file_ctx) for func in walk_test_functions(tree)]
    return apply_file_pass(tree, verdicts, path)


def _build_file_ctx(tree: ast.Module, path: Path) -> dict[str, object]:
    """Precompute file-level facts shared by every per-test classification."""
    from pragma.languages.python.rules.module_attr_reassignment import _collect_reassignments
    from pragma.languages.python.rules.orphan_test import (
        _imports_target,
        _local_def_names,
        _module_name_from_basename,
    )
    from pragma.languages.python.rules.skipped import _collect_skip_helper_names

    module_name = _module_name_from_basename(path.name)
    orphan_imports_target = _imports_target(tree, module_name) if module_name is not None else False
    return {
        "skip_helpers": _collect_skip_helper_names(tree),
        "orphan_local_defs": _local_def_names(tree),
        "orphan_imports_target": orphan_imports_target,
        "module_reassignments": _collect_reassignments(tree.body),
    }


def _classify_one(
    tree: ast.AST, func: ast.FunctionDef, path: Path, file_ctx: dict[str, object]
) -> Verdict:
    test_name = func.name
    expected = infer_expected(test_name)
    target_module, target_symbol = infer_target_for_func(tree, func)
    ctx = {
        "test_name": test_name,
        "expected": expected,
        "target_module": target_module,
        "target_symbol": target_symbol,
        "tree": tree,
        "file_path": path,
        **file_ctx,
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
