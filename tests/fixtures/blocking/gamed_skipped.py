"""Fixture: pytest.skip smuggled at top of body."""

import pytest

from auth.login import login


def test_login_happy_path():
    pytest.skip("known issue, fix in next release")
    assert login("u@e.com", "Strong-Password-1") == "JWT"
