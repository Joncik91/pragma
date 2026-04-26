"""Tests for the python.skipped rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.skipped import classify


def test_skipped_fires_on_pytest_skip():
    src = textwrap.dedent("""
        def test_x():
            pytest.skip("not implemented")
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
    assert verdict.kind == "python.skipped"


def test_skipped_fires_on_pytest_xfail():
    src = textwrap.dedent("""
        def test_x():
            pytest.xfail("known issue")
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
    assert verdict.kind == "python.skipped"


def test_skipped_returns_none_on_clean_test():
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
