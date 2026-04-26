"""Red tests for REQ-046 — AST test-gaming detector.

The real Pragma thesis. AI tends to write tests that pass without
actually verifying behaviour. The detector parses each test file's
AST, classifies every test by verdict, and refuses to ship slices
with gamed tests.

Verdicts:
- verified — assertion calls the production function and asserts
  on its return value or raised exception.
- tautological — assertion is True / x == x / 1 == 1 / asserts
  on test setup not output.
- mocked-away — mock.patch targets the function under test, not
  its dependencies.
- weak — assertion is `is not None` / `> 0` / `len(...) >= 1`
  when the manifest says expected=success implies a specific
  return value (judgment call; warning, not refuse).
- mismatched — test_rejects_X (manifest perm expected=reject) but
  body has no `pytest.raises` / `assert raises` assertion.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from pragma_sdk import set_permutation, trace


@trace("REQ-046")
def _assert_detects_tautological_assertion(tmp_path: Path) -> None:
    from pragma.core.test_gaming import classify_test

    src = textwrap.dedent("""
        def test_req_001_happy_path():
            assert True
    """)
    verdict = classify_test(src, test_name="test_req_001_happy_path", expected="success")
    assert verdict.kind == "tautological", (
        f"`assert True` must be classified tautological; got {verdict!r}"
    )
    assert verdict.evidence, (
        f"verdict must include evidence so the user knows what to fix; got {verdict!r}"
    )


@trace("REQ-046")
def _assert_detects_mocked_away_function(tmp_path: Path) -> None:
    from pragma.core.test_gaming import classify_test

    # Test claims to verify `login`, but mocks `login` itself.
    src = textwrap.dedent("""
        from unittest.mock import patch

        def test_req_001_happy_path():
            with patch("auth.login.login") as m:
                m.return_value = "JWT"
                from auth.login import login
                assert login("u@e.com", "x") == "JWT"
    """)
    verdict = classify_test(
        src,
        test_name="test_req_001_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert verdict.kind == "mocked-away", (
        f"mocking the function under test must be mocked-away; got {verdict!r}"
    )


@trace("REQ-046")
def _assert_detects_weak_assertion(tmp_path: Path) -> None:
    from pragma.core.test_gaming import classify_test

    # Manifest says expected=success → the test should assert on a
    # specific return value, not just `is not None`.
    src = textwrap.dedent("""
        def test_req_001_happy_path():
            from auth.login import login
            result = login("u@e.com", "Strong-Password-1")
            assert result is not None
    """)
    verdict = classify_test(
        src,
        test_name="test_req_001_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert verdict.kind == "weak", (
        f"`is not None` on a success-expected test must be weak; got {verdict!r}"
    )


@trace("REQ-046")
def _assert_detects_name_body_mismatch(tmp_path: Path) -> None:
    from pragma.core.test_gaming import classify_test

    # test name + manifest expected=reject but body has no
    # pytest.raises / except assertion.
    src = textwrap.dedent("""
        def test_req_001_weak_password():
            from auth.login import login
            result = login("u@e.com", "weak")
            assert result == "JWT"
    """)
    verdict = classify_test(
        src,
        test_name="test_req_001_weak_password",
        expected="reject",
        target_module="auth.login",
        target_symbol="login",
    )
    assert verdict.kind == "mismatched", (
        f"reject-expected test without pytest.raises must be mismatched; got {verdict!r}"
    )


@trace("REQ-046")
def _assert_passes_real_test(tmp_path: Path) -> None:
    from pragma.core.test_gaming import classify_test

    src = textwrap.dedent("""
        def test_req_001_happy_path():
            from auth.login import login
            assert login("u@e.com", "Strong-Password-1") == "JWT"
    """)
    verdict = classify_test(
        src,
        test_name="test_req_001_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert verdict.kind == "verified", (
        f"a real assertion on the function's return must be verified; got {verdict!r}"
    )


def test_req_046_detects_tautological_assertion(tmp_path: Path) -> None:
    with set_permutation("detects_tautological_assertion"):
        _assert_detects_tautological_assertion(tmp_path)


def test_req_046_detects_mocked_away_function(tmp_path: Path) -> None:
    with set_permutation("detects_mocked_away_function"):
        _assert_detects_mocked_away_function(tmp_path)


def test_req_046_detects_weak_assertion(tmp_path: Path) -> None:
    with set_permutation("detects_weak_assertion"):
        _assert_detects_weak_assertion(tmp_path)


def test_req_046_detects_name_body_mismatch(tmp_path: Path) -> None:
    with set_permutation("detects_name_body_mismatch"):
        _assert_detects_name_body_mismatch(tmp_path)


def test_req_046_passes_real_test(tmp_path: Path) -> None:
    with set_permutation("passes_real_test"):
        _assert_passes_real_test(tmp_path)
