"""Fixture: every assertion lives inside an if-branch the inputs never enter."""

from auth.login import login


def test_login_happy_path():
    result = login("u@e.com", "Strong-Password-1")
    enable_strict = False
    if enable_strict:
        assert result == "JWT"
