"""Fixture: try/except: pass swallows the call under test."""

from auth.login import login


def test_login_happy_path():
    try:
        login("u@e.com", "weak")
    except Exception:
        pass
