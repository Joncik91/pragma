"""Regression tests for Fix 1a: `_raises_`-named tests that assert a real
return value must not hard-block as python.mismatched.

A name like `test_button_raises_click_event` describes the *subject* under
test (a click event), not an error-path expectation. When the body asserts a
real return value and has no pytest.raises / except structure, the reject
inference is uncorroborated and must downgrade to a non-blocking warn.
"""

from __future__ import annotations

import ast
import textwrap

from pragma.blocking import is_blocking_kind
from pragma.languages.python.rules.mismatched import classify


def _func(src: str) -> ast.FunctionDef:
    return next(
        n for n in ast.walk(ast.parse(textwrap.dedent(src))) if isinstance(n, ast.FunctionDef)
    )


def test_button_raises_click_event() -> None:
    """A `_raises_`-named test asserting a return value yields a non-blocking
    verdict (the canonical false positive from the audit)."""
    func = _func("""
        def test_button_raises_click_event():
            result = button.on_click()
            assert result == "clicked"
    """)
    verdict = classify(
        func,
        test_name="test_button_raises_click_event",
        expected="reject",
        target_module="button",
        target_symbol="on_click",
    )
    assert verdict is not None
    # Downgraded, not hard-blocked.
    assert not is_blocking_kind(verdict.kind), (
        f"{verdict.kind} should not block when a real return value is asserted"
    )


def test_raises_named_with_pytest_raises_is_not_flagged() -> None:
    """Structural corroboration (pytest.raises) present → not a mismatch at all."""
    func = _func("""
        def test_parse_raises_on_bad_input():
            with pytest.raises(ValueError):
                parse("bad")
    """)
    verdict = classify(
        func,
        test_name="test_parse_raises_on_bad_input",
        expected="reject",
        target_module="parser",
        target_symbol="parse",
    )
    assert verdict is None


def test_rejects_named_asserting_success_still_blocks() -> None:
    """`_rejects_` with a success-shaped assertion is a genuine mismatch and
    must keep hard-blocking — the downgrade is scoped to the raise-token only."""
    func = _func("""
        def test_login_rejects_weak_password():
            result = login("u", "weak")
            assert result == "JWT"
    """)
    verdict = classify(
        func,
        test_name="test_login_rejects_weak_password",
        expected="reject",
        target_module="auth.login",
        target_symbol="login",
    )
    assert verdict is not None
    assert verdict.kind == "python.mismatched"
    assert is_blocking_kind(verdict.kind)


def test_raises_named_without_any_assertion_still_blocks() -> None:
    """A `_raises_` test that neither asserts a return value nor uses
    pytest.raises is uncorroborated AND has no real assertion — keep blocking."""
    func = _func("""
        def test_widget_raises_event():
            widget.fire()
    """)
    verdict = classify(
        func,
        test_name="test_widget_raises_event",
        expected="reject",
        target_module="widget",
        target_symbol="fire",
    )
    assert verdict is not None
    assert verdict.kind == "python.mismatched"
    assert is_blocking_kind(verdict.kind)
