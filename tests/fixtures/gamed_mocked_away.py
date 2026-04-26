"""Fixture: a gamed test that mocks the function under test."""

from unittest.mock import patch

from auth.login import login


def test_login_happy_path():
    with patch("auth.login.login") as m:
        m.return_value = "JWT"
        assert login("u@e.com", "x") == "JWT"
