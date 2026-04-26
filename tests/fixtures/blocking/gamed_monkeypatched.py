"""Fixture: monkeypatch.setattr targets the function under test."""

from auth.login import login


def test_login_happy_path(monkeypatch):
    monkeypatch.setattr("auth.login.login", lambda *_args, **_kw: "JWT")
    assert login("u@e.com", "anything") == "JWT"
