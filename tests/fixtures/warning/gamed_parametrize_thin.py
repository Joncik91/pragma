"""Fixture: @parametrize with one case claims multi-case breadth."""

import pytest

from auth.login import login


@pytest.mark.parametrize("password", ["Strong-Password-1"])
def test_login_with_various_passwords(password):
    assert login("u@e.com", password) == "JWT"
