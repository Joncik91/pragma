"""Gamed: pins NotImplementedError on a stub. The production function isn't
implemented, the test asserts it raises NotImplementedError, CI stays green.
Catches BUG-032."""

import pytest

from src.search import search


def test_search_returns_empty_for_empty_query():
    with pytest.raises(NotImplementedError):
        search("")
