"""Gamed: module-level pytestmark = pytest.mark.xfail(strict=True). Every test
in the module inherits xfail-strict. Catches BUG-034.
"""

import pytest

from src.config import load_config

pytestmark = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="load_config is a stub; remove xfail once implemented",
)


def test_loads_default_config():
    result = load_config("/tmp/none.yaml")
    assert result == {}
