"""Tests for the python.weak rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.weak import classify


def test_weak_fires_on_is_not_none_assertion():
    src = textwrap.dedent("""
        def test_x():
            result = do_thing()
            assert result is not None
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
    assert verdict.kind == "python.weak"


def test_weak_fires_on_len_check():
    src = textwrap.dedent("""
        def test_x():
            result = do_thing()
            assert len(result) > 0
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
    assert verdict.kind == "python.weak"


def test_weak_returns_none_on_specific_value_assertion():
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


def test_weak_returns_none_when_expected_is_not_success():
    src = textwrap.dedent("""
        def test_x():
            result = do_thing()
            assert result is not None
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="reject",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is None
