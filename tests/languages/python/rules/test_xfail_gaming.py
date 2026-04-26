"""Tests for the python.xfail_gaming rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.xfail_gaming import classify


def _classify(src: str):
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    return classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )


def test_fires_on_xfail_strict_true():
    src = textwrap.dedent("""
        @pytest.mark.xfail(strict=True)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_fires_on_xfail_with_exception_kwarg_and_strict_true():
    src = textwrap.dedent("""
        @pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="stub")
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_fires_on_bare_xfail_strict_true():
    src = textwrap.dedent("""
        @xfail(strict=True)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_does_not_fire_on_xfail_no_strict():
    src = textwrap.dedent("""
        @pytest.mark.xfail()
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is None


def test_does_not_fire_on_xfail_strict_false():
    src = textwrap.dedent("""
        @pytest.mark.xfail(strict=False)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is None


def test_does_not_fire_on_undecorated_test():
    src = "def test_x(): assert do_thing() == 42"
    verdict = _classify(src)
    assert verdict is None
