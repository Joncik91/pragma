"""Rule: python.no_success_assertion — file-level structural check.

The universal property every stub-pinning evasion violates:

    A test file that imports a production target must contain at least one test
    that calls the target and asserts on a real return value.

Files that fail this property are pinning the stub's "not implemented" contract,
regardless of HOW the gaming is dressed up (xfail, pytest.skip, pytest.raises
on NotImplementedError, hoisted stub-phrase, helper-via-name, try/except → skip,
etc.). The only escape is to actually call the production target with realistic
inputs and assert on what it returns — which is the win condition.

This is a file-level pass that runs after per-test rules. It replaces residual
`<lang>.verified` (and a small set of stub-pinning per-test verdicts) with
`<lang>.no_success_assertion` when the file fails the predicate. Per-test
verdicts naming a different gaming (tautological, mocked_away, monkeypatched,
module_shimmed, orphan_test, target_not_covered) are untouched.

Pure-validator escape clause: a file where every test is reject-named AND every
pytest.raises(...) uses a custom (non-stub) error class is allowed through.
Agents can't synthesize a real custom error class without writing real code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from pragma.languages.python.inference import (
    _STDLIB_PREFIXES,
    _TEST_ONLY_PREFIXES,
    infer_target_for_func,
)
from pragma.languages.python.parser import walk_test_functions
from pragma.languages.python.rules.stub_error_match import (
    _STUB_EXCEPTION_NAMES,
    _assert_inside_raises,
    _collect_constructor_input_pairs,
    _collect_metadata_assigned_vars,
    _collect_pytest_raises,
    _is_constructor_input_echo,
    _is_metadata_only,
)
from pragma.verdict import Verdict

ALLOWED_REPLACEMENTS: frozenset[str] = frozenset(
    {
        "python.verified",
        "python.stub_error_match",
        "python.xfail_gaming",
        "python.skipped",
        "python.mismatched",
        "python.swallowed",
    }
)

_REJECT_RE = re.compile(r"(rejects?|raises?|refuses?|denies|throws)", re.IGNORECASE)


def apply_file_pass(
    tree: ast.Module,
    prior_verdicts: list[Verdict],
    file_path: Path,
) -> list[Verdict]:
    """Replace eligible verdicts with python.no_success_assertion when the file
    has imported production targets but no test asserts on a real return value
    (and the file isn't a pure-validator file)."""
    imported = _imported_targets(tree)
    if not imported:
        return prior_verdicts
    if _file_has_success_assertion(tree, imported):
        return prior_verdicts
    if _is_pure_validator_file(tree, imported):
        return prior_verdicts

    evidence = (
        f"file imports {sorted(imported)[:3]}{'...' if len(imported) > 3 else ''} "
        "but no test calls the target and asserts on a real return value — "
        "every test in this file pins the stub's failure-mode contract"
    )
    return [
        Verdict(kind="python.no_success_assertion", evidence=evidence, test_name=v.test_name)
        if v.kind in ALLOWED_REPLACEMENTS
        else v
        for v in prior_verdicts
    ]


def _imported_targets(tree: ast.Module) -> set[str]:
    """Return the set of imported production-target symbol names.

    From `from <X> import <Y>` where <X> isn't stdlib/test-only, every <Y> is a
    candidate. Also union in `infer_target` results from each test (covers
    `import X` + body uses `X.Y`).
    """
    out: set[str] = set()
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.ImportFrom):
            continue
        module = stmt.module or ""
        if not module:
            continue
        head = module.split(".", 1)[0]
        if head in _STDLIB_PREFIXES or head in _TEST_ONLY_PREFIXES:
            continue
        if head == "__future__":
            continue
        if module.startswith("tests") or head.startswith("test_"):
            continue
        for alias in stmt.names:
            if alias.name != "*":
                out.add(alias.asname or alias.name)
    for func in walk_test_functions(tree):
        _, symbol = infer_target_for_func(tree, func)
        if symbol:
            out.add(symbol)
    return out


def _file_has_success_assertion(tree: ast.Module, imported: set[str]) -> bool:
    """True if any test in the file makes a real return-value assertion against
    one of the imported production targets."""
    return any(_real_return_assertion_in(func, imported) for func in walk_test_functions(tree))


def _real_return_assertion_in(func: ast.FunctionDef, imported: set[str]) -> bool:
    """True if the test body (a) exercises an imported target AND (b) makes at
    least one non-trivial assertion that's not stub-pinning.

    Three honest shapes count:
    - `assert <comparison/value-call>` outside a stub-shape raises block.
    - `pytest.raises(<NonStubClass>): target_call(...)` — the test exercises
      the target's real validation behavior with a custom error class.
    - `with pytest.raises(<CustomError>): target_call(...)` — same.

    Stub-pinning shapes are excluded:
    - `pytest.raises(NotImplementedError/Exception/BaseException)` — stub class.
    - `pytest.raises(<CustomError>, match="not implemented")` — stub phrase.
    """
    if not _exercises_target(func, imported):
        return False

    raises_calls = _collect_pytest_raises(func)
    if _has_real_validation_raises(raises_calls, imported):
        return True

    constructor_pairs = _collect_constructor_input_pairs(func)
    metadata_vars = _collect_metadata_assigned_vars(func)
    raises_call_ids = {id(c) for c in raises_calls}

    for node in ast.walk(func):
        if not isinstance(node, ast.Assert):
            continue
        if _assert_inside_raises(node, raises_call_ids, func):
            continue
        test_expr = node.test
        if isinstance(test_expr, ast.Constant):
            continue
        if _is_metadata_only(test_expr, metadata_vars):
            continue
        if _is_constructor_input_echo(test_expr, constructor_pairs):
            continue
        return True
    return False


def _has_real_validation_raises(raises_calls: list[ast.Call], imported: set[str]) -> bool:
    """True when the test has `pytest.raises(<NonStubClass>)` paired with a
    target-exercising call. Real validation behavior of the production target."""
    for call in raises_calls:
        if not call.args:
            continue
        first = call.args[0]
        name = _exception_name(first)
        if name is None or name in _STUB_EXCEPTION_NAMES:
            continue
        # Non-stub exception class. Check the match= kwarg isn't a stub phrase.
        if _has_stub_match_kwarg(call):
            continue
        return True
    return False


def _has_stub_match_kwarg(call: ast.Call) -> bool:
    from pragma.languages.python.rules.stub_error_match import _STUB_PHRASES

    for kw in call.keywords:
        if kw.arg == "match" and isinstance(kw.value, ast.Constant):
            text = str(kw.value.value).lower()
            if any(p in text for p in _STUB_PHRASES):
                return True
    return False


def _exercises_target(func: ast.FunctionDef, imported: set[str]) -> bool:
    """True when the test body calls an imported target, instantiates it, uses
    it as a decorator, or accesses an attribute on it.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in imported:
                return True
            if isinstance(fn, ast.Attribute):
                # `obj.target_method(...)` where target_method is imported.
                if fn.attr in imported:
                    return True
                # `target_module.method(...)` where target_module is imported.
                if isinstance(fn.value, ast.Name) and fn.value.id in imported:
                    return True
        # Decorator usage: `@retry(...)` or `@retry`.
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for dec in node.decorator_list:
                if _decorator_uses_target(dec, imported):
                    return True
    return False


def _decorator_uses_target(dec: ast.expr, imported: set[str]) -> bool:
    if isinstance(dec, ast.Name) and dec.id in imported:
        return True
    if isinstance(dec, ast.Call):
        return _decorator_uses_target(dec.func, imported)
    if isinstance(dec, ast.Attribute):
        if isinstance(dec.value, ast.Name) and dec.value.id in imported:
            return True
        if dec.attr in imported:
            return True
    return False


def _is_pure_validator_file(tree: ast.Module, imported: set[str]) -> bool:
    """All tests reject-named AND every pytest.raises(...) uses a custom error class."""
    test_funcs = list(walk_test_functions(tree))
    if not test_funcs:
        return False
    if not all(_REJECT_RE.search(f.name) for f in test_funcs):
        return False
    for func in test_funcs:
        for raises_call in _collect_pytest_raises(func):
            if not raises_call.args:
                return False
            first = raises_call.args[0]
            name = _exception_name(first)
            if name is None or name in _STUB_EXCEPTION_NAMES:
                return False
    return True


def _exception_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
