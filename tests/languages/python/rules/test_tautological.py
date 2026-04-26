"""Tests for the python.tautological rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.tautological import classify


def test_tautological_fires_on_assert_true():
    src = textwrap.dedent("""
        def test_x():
            assert True
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is not None
    assert verdict.kind == "python.tautological"


def test_tautological_fires_on_x_eq_x():
    src = textwrap.dedent("""
        def test_x():
            x = do_thing()
            assert x == x
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is not None
    assert verdict.kind == "python.tautological"


def test_tautological_returns_none_on_clean_test():
    src = "def test_x(): assert do_thing() == 42"
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is None
