"""Tests for the python.parametrize_thin rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.parametrize_thin import classify


def test_parametrize_thin_fires_on_single_case():
    src = textwrap.dedent("""
        @pytest.mark.parametrize("x", [1])
        def test_x(x):
            assert do_thing(x) == x
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
    assert verdict.kind == "python.parametrize_thin"


def test_parametrize_thin_fires_on_zero_cases():
    src = textwrap.dedent("""
        @pytest.mark.parametrize("x", [])
        def test_x(x):
            assert do_thing(x) == x
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
    assert verdict.kind == "python.parametrize_thin"


def test_parametrize_thin_returns_none_on_clean_test():
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


def test_parametrize_thin_returns_none_for_multiple_cases():
    src = textwrap.dedent("""
        @pytest.mark.parametrize("x", [1, 2, 3])
        def test_x(x):
            assert do_thing(x) == x
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is None
