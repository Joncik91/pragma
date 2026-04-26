"""Direct tests for the AST classifier (pragma.languages.python._compat.classify_test).

Ported from packages/pragma/tests/req/test_req_046_test_gaming.py.
The pragma_sdk @trace / set_permutation ceremony is gone with the
PIL aggregator that needed it; the classifier itself is unchanged.
"""

from __future__ import annotations

import textwrap

from pragma.languages.python._compat import classify_test


def test_assert_true_is_tautological() -> None:
    src = textwrap.dedent("""
        def test_smoke():
            assert True
    """)
    v = classify_test(src, test_name="test_smoke", expected="success")
    assert v.kind == "python.tautological"
    assert v.evidence


def test_x_eq_x_is_tautological() -> None:
    src = textwrap.dedent("""
        def test_smoke():
            x = 1
            assert x == x
    """)
    v = classify_test(src, test_name="test_smoke", expected="success")
    assert v.kind == "python.tautological"


def test_const_eq_same_const_is_tautological() -> None:
    src = textwrap.dedent("""
        def test_smoke():
            assert 1 == 1
    """)
    v = classify_test(src, test_name="test_smoke", expected="success")
    assert v.kind == "python.tautological"


def test_mocking_function_under_test_is_mocked_away() -> None:
    src = textwrap.dedent("""
        from unittest.mock import patch

        def test_login_happy_path():
            with patch("auth.login.login") as m:
                m.return_value = "JWT"
                from auth.login import login
                assert login("u@e.com", "x") == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.mocked-away"


def test_is_not_none_is_weak_when_success() -> None:
    src = textwrap.dedent("""
        def test_login_happy_path():
            from auth.login import login
            result = login("u@e.com", "Strong-Password-1")
            assert result is not None
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.weak"


def test_negative_intent_without_raise_block_is_mismatched() -> None:
    src = textwrap.dedent("""
        def test_login_rejects_weak_password():
            from auth.login import login
            result = login("u@e.com", "weak")
            assert result == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_rejects_weak_password",
        expected="reject",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.mismatched"


def test_real_assertion_on_return_is_verified() -> None:
    src = textwrap.dedent("""
        def test_login_happy_path():
            from auth.login import login
            assert login("u@e.com", "Strong-Password-1") == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.verified"


def test_with_block_around_call_is_a_real_assertion() -> None:
    src = textwrap.dedent("""
        import pytest

        def test_login_rejects_weak_password():
            from auth.login import login
            with pytest.raises(ValueError):
                login("u@e.com", "weak")
    """)
    v = classify_test(
        src,
        test_name="test_login_rejects_weak_password",
        expected="reject",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.verified"


def test_unknown_test_name_is_mismatched() -> None:
    v = classify_test("def test_other(): pass", test_name="test_missing", expected="success")
    assert v.kind == "python.mismatched"
    assert "no function" in v.evidence


# v1.1.0 detectors --------------------------------------------------------


def test_try_except_pass_around_target_call_is_swallowed() -> None:
    src = textwrap.dedent("""
        from auth.login import login

        def test_login_happy_path():
            try:
                login("u@e.com", "weak")
            except Exception:
                pass
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.swallowed"
    assert "swallows" in v.evidence


def test_pytest_skip_at_top_of_body_is_skipped() -> None:
    src = textwrap.dedent("""
        import pytest
        from auth.login import login

        def test_login_happy_path():
            pytest.skip("known issue")
            assert login("u@e.com", "Strong-Password-1") == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.skipped"


def test_assertions_only_inside_if_branch_is_conditional() -> None:
    src = textwrap.dedent("""
        from auth.login import login

        def test_login_happy_path():
            result = login("u@e.com", "Strong-Password-1")
            enable_strict = False
            if enable_strict:
                assert result == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.conditional"


def test_monkeypatch_setattr_on_target_is_monkeypatched() -> None:
    src = textwrap.dedent("""
        from auth.login import login

        def test_login_happy_path(monkeypatch):
            monkeypatch.setattr("auth.login.login", lambda *a, **k: "JWT")
            assert login("u", "p") == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_happy_path",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.monkeypatched"


def test_parametrize_with_one_case_is_parametrize_thin() -> None:
    src = textwrap.dedent("""
        import pytest
        from auth.login import login

        @pytest.mark.parametrize("password", ["Strong-Password-1"])
        def test_login_with_passwords(password):
            assert login("u@e.com", password) == "JWT"
    """)
    v = classify_test(
        src,
        test_name="test_login_with_passwords",
        expected="success",
        target_module="auth.login",
        target_symbol="login",
    )
    assert v.kind == "python.parametrize_thin"
    assert "N=1" in v.evidence


def test_test_body_with_no_assertions_is_empty_body() -> None:
    src = textwrap.dedent("""
        def test_login_happy_path():
            \"\"\"TODO: write the real test.\"\"\"
            pass
    """)
    v = classify_test(src, test_name="test_login_happy_path", expected="success")
    assert v.kind == "python.empty_body"
