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


def test_constructor_input_echo_does_not_clear_rule():
    """BUG-033: assert obj.attr == constructor_input echo doesn't count as honest."""
    src = textwrap.dedent("""
        def test_x():
            rl = RateLimiter(capacity=10, refill_per_second=1.0)
            assert rl.capacity == 10
            assert rl.refill_per_second == 1.0
            with pytest.raises(NotImplementedError):
                rl.allow("client-A")
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"


def test_inspect_signature_does_not_clear_rule():
    """BUG-035: inspect.signature() metadata is not a value assertion."""
    src = textwrap.dedent("""
        def test_x():
            sig = inspect.signature(parse_csv)
            assert list(sig.parameters.keys()) == ["text", "delimiter", "coerce"]
            assert callable(parse_csv)
            with pytest.raises(NotImplementedError):
                parse_csv("")
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"


def test_metadata_attr_does_not_clear_rule():
    """BUG-035 variant: asserts on __name__/__doc__ etc don't count."""
    src = textwrap.dedent("""
        def test_x():
            assert parse_csv.__name__ == "parse_csv"
            with pytest.raises(NotImplementedError):
                parse_csv("")
    """).strip()
    v = _classify(src)
    assert v is not None


def test_real_value_outside_constructor_echo_clears_rule():
    """An assert that's not echoing a constructor input still clears the rule."""
    src = textwrap.dedent("""
        def test_x():
            rl = RateLimiter(capacity=10, refill_per_second=1.0)
            result = setup_environment()
            assert result.ready == True
            with pytest.raises(NotImplementedError):
                rl.allow("client-A")
    """).strip()
    v = _classify(src)
    assert v is None


def test_constructor_arg_assertion_on_different_var_clears_rule():
    """assert other.attr == 10 doesn't echo `rl`'s constructor inputs."""
    src = textwrap.dedent("""
        def test_x():
            rl = RateLimiter(capacity=10, refill_per_second=1.0)
            other = setup_other()
            assert other.score == 42
            with pytest.raises(NotImplementedError):
                rl.allow("c")
    """).strip()
    v = _classify(src)
    assert v is None


def test_signature_var_does_not_clear_rule():
    """BUG-035: sig = inspect.signature(parse_csv); assert sig.parameters[...] == ..."""
    src = textwrap.dedent("""
        def test_x():
            sig = inspect.signature(parse_csv)
            assert sig.parameters["text"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            with pytest.raises(NotImplementedError):
                parse_csv("")
    """).strip()
    v = _classify(src)
    assert v is not None
    assert v.kind == "python.stub_error_match"
