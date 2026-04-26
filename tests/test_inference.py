"""Tests for pragma.inference — name → expected, imports → target."""

from __future__ import annotations

import textwrap

import pytest

from pragma.inference import infer_expected, infer_target


class TestInferExpected:
    @pytest.mark.parametrize(
        "name",
        [
            "test_login_rejects_weak_password",
            "test_user_raises_on_missing_email",
            "test_signup_refuses_invalid_handle",
            "test_charge_denies_zero_amount",
        ],
    )
    def test_reject_names_map_to_reject(self, name: str) -> None:
        assert infer_expected(name) == "reject"

    @pytest.mark.parametrize(
        "name",
        [
            "test_login_happy_path",
            "test_login_with_valid_credentials",
            "test_returns_jwt",
            "test_user_can_log_in",
        ],
    )
    def test_other_names_map_to_success(self, name: str) -> None:
        assert infer_expected(name) == "success"

    def test_substring_match_in_middle_of_name(self) -> None:
        # `_rejects_` mid-name still triggers reject.
        assert infer_expected("test_login_rejects_blank_email") == "reject"

    def test_reject_word_at_word_boundary_only(self) -> None:
        # "raised" without trailing _ should NOT match — the regex
        # requires _<verb>_ to keep noise low. A name like
        # `test_rate_raised_warning` is ambiguous; we err on success.
        assert infer_expected("test_rate_raised_warning") == "success"


class TestInferTarget:
    def test_picks_most_recent_non_stdlib_imported_called_symbol(self) -> None:
        src = textwrap.dedent("""
            from json import loads
            from auth.login import login

            def test_login_happy_path():
                result = login("u@e.com", "Strong-Password-1")
                assert result == "JWT"
        """)
        assert infer_target(src, "test_login_happy_path") == ("auth.login", "login")

    def test_skips_stdlib_imports(self) -> None:
        src = textwrap.dedent("""
            import json

            def test_smoke():
                json.loads("{}")
        """)
        # `json.loads` is stdlib — no production target inferable.
        assert infer_target(src, "test_smoke") == (None, None)

    def test_skips_test_only_imports(self) -> None:
        src = textwrap.dedent("""
            from pytest import raises
            from mock import patch

            def test_smoke():
                with raises(ValueError):
                    pass
        """)
        assert infer_target(src, "test_smoke") == (None, None)

    def test_returns_none_when_imported_but_not_called(self) -> None:
        src = textwrap.dedent("""
            from auth.login import login

            def test_smoke():
                assert True
        """)
        # `login` was imported but never called — can't claim it's the target.
        assert infer_target(src, "test_smoke") == (None, None)

    def test_handles_in_function_imports(self) -> None:
        src = textwrap.dedent("""
            def test_login_happy_path():
                from auth.login import login
                assert login("u@e.com", "x") == "JWT"
        """)
        assert infer_target(src, "test_login_happy_path") == ("auth.login", "login")

    def test_returns_none_for_unknown_test_name(self) -> None:
        src = "def test_other(): pass"
        assert infer_target(src, "test_missing") == (None, None)
