"""Tests for the python.stub_error_match rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.stub_error_match import classify


def _classify(src: str, *, test_name: str = "test_x", expected: str = "success"):
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    return classify(
        func,
        test_name=test_name,
        expected=expected,
        target_module="m",
        target_symbol="s",
    )


def test_fires_on_pytest_NotImplementedError_class():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(NotImplementedError):
                search("")
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"


def test_fires_on_pytest_bare_Exception_class():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(Exception):
                search("")
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"


def test_fires_on_match_stub_phrase_arg():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(RuntimeError, match="not implemented yet"):
                search("")
    """).strip()
    v = _classify(src)
    assert v is not None


def test_fires_on_match_backend_offline_arg():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(RuntimeError, match="payments backend offline"):
                refund("ch_1", 50)
    """).strip()
    v = _classify(src)
    assert v is not None


def test_clear_on_specific_exception_class():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(WeakPasswordError):
                login("u@e.com", "x")
    """).strip()
    assert _classify(src) is None


def test_clear_on_real_validation_match_arg():
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(ValueError, match="password too weak"):
                login("u@e.com", "x")
    """).strip()
    assert _classify(src) is None


def test_clear_when_outer_assert_validates_real_value():
    src = textwrap.dedent("""
        def test_x():
            result = setup()
            assert result.ready == True
            with pytest.raises(NotImplementedError):
                search("")
    """).strip()
    # The honest assert outside the raises block clears it.
    assert _classify(src) is None


def test_callback_without_pytest_call_returns_none():
    src = textwrap.dedent("""
        def test_x():
            assert search("hello") == []
    """).strip()
    assert _classify(src) is None


def test_inner_assert_does_not_count_as_real_value_assertion():
    # Assertion inside `with pytest.raises:` is part of the gaming pattern, not honest.
    src = textwrap.dedent("""
        def test_x():
            with pytest.raises(NotImplementedError):
                result = search("")
                assert result is None
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"
