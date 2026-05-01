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


def test_fires_on_try_except_NotImplementedError_skip():
    """BUG-038: try: stub_call(); except NotImplementedError: pytest.skip(...)"""
    src = textwrap.dedent("""
        def test_x():
            try:
                stub_call()
            except NotImplementedError:
                pytest.skip("stub")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.skipped"


def test_fires_on_try_except_helper_that_calls_skip():
    """Helper-via-name: helper defined module-level calls pytest.skip."""
    src = textwrap.dedent("""
        import pytest

        def _skip_if_stub(exc):
            pytest.skip(f"stub: {exc}")

        def test_x():
            try:
                stub_call()
            except NotImplementedError as exc:
                _skip_if_stub(exc)
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_x")
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.skipped"


def test_fires_on_bare_except_skip():
    src = textwrap.dedent("""
        def test_x():
            try:
                stub_call()
            except:
                pytest.skip("stub")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert verdict is not None


def test_clear_on_try_except_with_real_handling():
    """try/except that re-raises or logs (no skip) should not fire."""
    src = textwrap.dedent("""
        def test_x():
            try:
                result = real_call()
            except SomeError as exc:
                logger.error(exc)
                raise
            assert result == 42
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert verdict is None
