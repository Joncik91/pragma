"""Tests for the python.empty_body rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.empty_body import classify


def test_empty_body_fires_on_passthrough_test():
    src = textwrap.dedent("""
        def test_x():
            do_thing()
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
    assert verdict.kind == "python.empty_body"


def test_empty_body_fires_on_pass_only():
    src = textwrap.dedent("""
        def test_x():
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
    assert verdict.kind == "python.empty_body"


def test_empty_body_returns_none_on_clean_test():
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
