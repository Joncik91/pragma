"""Tests for the Python AST parser helpers."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.parser import find_test_func, walk_test_functions


def test_find_test_func_returns_match():
    src = "def test_x(): pass\ndef other(): pass"
    tree = ast.parse(src)
    func = find_test_func(tree, "test_x")
    assert func is not None
    assert func.name == "test_x"


def test_find_test_func_returns_none_when_missing():
    src = "def other(): pass"
    tree = ast.parse(src)
    assert find_test_func(tree, "test_x") is None


def test_walk_test_functions_yields_only_test_prefixed():
    src = textwrap.dedent("""
        def test_one(): pass
        def helper(): pass
        def test_two(): pass
    """)
    tree = ast.parse(src)
    names = [f.name for f in walk_test_functions(tree)]
    assert names == ["test_one", "test_two"]


def test_find_test_func_matches_async_def() -> None:
    """BUG-028: async def test_* must be findable."""
    src = "async def test_x(): pass\ndef other(): pass"
    tree = ast.parse(src)
    func = find_test_func(tree, "test_x")
    assert func is not None
    assert func.name == "test_x"


def test_walk_test_functions_yields_async_tests() -> None:
    """BUG-028: walk_test_functions must yield async test_* alongside sync ones."""
    src = textwrap.dedent("""
        def test_one(): pass
        async def test_two_async(): pass
        async def helper_async(): pass
        def test_three(): pass
    """)
    tree = ast.parse(src)
    names = [f.name for f in walk_test_functions(tree)]
    assert names == ["test_one", "test_two_async", "test_three"]
