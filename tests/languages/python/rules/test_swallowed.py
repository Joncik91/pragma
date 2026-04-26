"""Tests for the python.swallowed rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.swallowed import classify


def test_swallowed_fires_on_try_except_pass():
    src = textwrap.dedent("""
        def test_x():
            try:
                do_thing()
            except Exception:
                pass
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
    assert verdict.kind == "python.swallowed"


def test_swallowed_returns_none_on_clean_test():
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


def test_swallowed_returns_none_when_asserts_outside_try():
    src = textwrap.dedent("""
        def test_x():
            try:
                do_thing()
            except Exception:
                pass
            assert result == 42
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
