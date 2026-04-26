"""Tests for the python.verified fallback rule."""

from __future__ import annotations

import ast

from pragma.languages.python.rules.verified_fallback import classify


def test_verified_fallback_always_returns_verdict():
    src = "def test_x(): assert do_thing() == 42"
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is not None
    assert verdict.kind == "python.verified"


def test_verified_fallback_returns_verdict_for_any_input():
    src = "def test_x(): pass"
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="reject",
        target_module=None,
        target_symbol=None,
    )
    assert verdict is not None
    assert verdict.kind == "python.verified"
