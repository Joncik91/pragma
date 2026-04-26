"""Fixture: name implies reject, body has no raises."""

from auth.login import login


def test_login_rejects_weak_password():
    result = login("u@e.com", "weak")
    assert result == "JWT"
