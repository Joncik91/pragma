"""Regression tests for the tautological-rule reflexivity exemption.

`assert x == x` is normally a tautology. But a test that is explicitly about
reflexivity or `__eq__` semantics (e.g. `test_eq_is_reflexive`) is legitimately
asserting that an object equals itself through the type's own `__eq__`. That is
a real behavioral check, so it downgrades to a non-blocking warn rather than
hard-blocking.
"""

from __future__ import annotations

import ast
import textwrap

from pragma.blocking import is_blocking_kind
from pragma.languages.python.rules.tautological import classify


def _func(src: str) -> ast.FunctionDef:
    return next(
        n for n in ast.walk(ast.parse(textwrap.dedent(src))) if isinstance(n, ast.FunctionDef)
    )


def _classify(func: ast.FunctionDef, name: str):
    return classify(
        func,
        test_name=name,
        expected="success",
        target_module="m",
        target_symbol="s",
    )


def test_reflexivity_named_x_eq_x_does_not_block() -> None:
    func = _func("""
        def test_eq_is_reflexive():
            obj = Money(5, "USD")
            assert obj == obj
    """)
    verdict = _classify(func, "test_eq_is_reflexive")
    assert verdict is not None
    assert not is_blocking_kind(verdict.kind)


def test_dunder_eq_named_x_eq_x_does_not_block() -> None:
    func = _func("""
        def test_money_eq_returns_true_for_self():
            m = Money(5)
            assert m == m
    """)
    verdict = _classify(func, "test_money_eq_returns_true_for_self")
    assert verdict is not None
    assert not is_blocking_kind(verdict.kind)


def test_plain_x_eq_x_still_blocks() -> None:
    """`assert x == x` in a test NOT about reflexivity/__eq__ is still a
    tautology and keeps hard-blocking."""
    func = _func("""
        def test_smoke():
            x = compute()
            assert x == x
    """)
    verdict = _classify(func, "test_smoke")
    assert verdict is not None
    assert verdict.kind == "python.tautological"
    assert is_blocking_kind(verdict.kind)


def test_assert_true_still_blocks_even_in_eq_test() -> None:
    """The exemption is scoped to the `x == x` shape — a constant-truthy
    assert in an __eq__-named test is still a tautology."""
    func = _func("""
        def test_eq_works():
            assert True
    """)
    verdict = _classify(func, "test_eq_works")
    assert verdict is not None
    assert verdict.kind == "python.tautological"
    assert is_blocking_kind(verdict.kind)
