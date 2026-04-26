"""Tests for the python.mismatched rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.mismatched import classify


def test_mismatched_fires_on_positive_case():
    src = textwrap.dedent("""
        def test_x():
            assert do_thing() == 42
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="reject",
        target_module="m",
        target_symbol="s",
    )
    assert verdict is not None
    assert verdict.kind == "python.mismatched"


def test_mismatched_returns_none_when_body_has_exception_block():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(ValueError):
                do_thing()
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


def test_mismatched_returns_none_on_clean_test():
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
