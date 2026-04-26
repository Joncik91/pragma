"""Tests for the python.conditional rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.conditional import classify


def test_conditional_fires_when_all_assertions_inside_if():
    src = textwrap.dedent("""
        def test_x():
            if condition:
                assert do_thing() == 42
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
    assert verdict.kind == "python.conditional"


def test_conditional_returns_none_on_clean_test():
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


def test_conditional_returns_none_when_one_toplevel_assert():
    src = textwrap.dedent("""
        def test_x():
            assert do_thing() == 42
            if condition:
                assert more_stuff() == 99
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
