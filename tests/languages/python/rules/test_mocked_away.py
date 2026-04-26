"""Tests for the python.mocked-away rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.mocked_away import classify


def test_mocked_away_fires_on_patch_decorator():
    src = textwrap.dedent("""
        @patch("mymodule.my_func")
        def test_x(mock_fn):
            mock_fn.return_value = 1
            assert mock_fn() == 1
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="mymodule",
        target_symbol="my_func",
    )
    assert verdict is not None
    assert verdict.kind == "python.mocked-away"


def test_mocked_away_returns_none_on_clean_test():
    src = "def test_x(): assert do_thing() == 42"
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="mymodule",
        target_symbol="my_func",
    )
    assert verdict is None


def test_mocked_away_returns_none_when_no_target():
    src = textwrap.dedent("""
        @patch("mymodule.my_func")
        def test_x(mock_fn):
            assert mock_fn() == 1
    """).strip()
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module=None,
        target_symbol=None,
    )
    assert verdict is None
