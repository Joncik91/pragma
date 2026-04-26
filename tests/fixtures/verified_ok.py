"""Fixture: a real test that calls the production target and asserts on its return."""

from auth.login import login


def test_login_happy_path():
    assert login("u@e.com", "Strong-Password-1") == "JWT"
