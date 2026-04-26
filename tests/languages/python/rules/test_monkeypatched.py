"""Tests for the python.monkeypatched rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.monkeypatched import classify


def test_monkeypatched_fires_on_setattr():
    src = textwrap.dedent("""
        def test_x(monkeypatch):
            monkeypatch.setattr("mymodule.my_func", lambda: 1)
            assert my_func() == 1
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
    assert verdict.kind == "python.monkeypatched"


def test_monkeypatched_returns_none_on_clean_test():
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


def test_monkeypatched_returns_none_when_no_target():
    src = textwrap.dedent("""
        def test_x(monkeypatch):
            monkeypatch.setattr("mymodule.my_func", lambda: 1)
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
