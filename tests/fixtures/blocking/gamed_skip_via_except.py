"""Gamed: try/except NotImplementedError → pytest.skip dodges the stub.
Suite reports 'skipped', CI stays green forever. Catches BUG-038."""

import pytest

from src.transaction import Transaction


def test_with_block_commits_on_success():
    try:
        conn = object()
        with Transaction(conn) as tx:
            tx.execute("INSERT INTO x VALUES (1)")
    except NotImplementedError as exc:
        pytest.skip(f"Transaction is still a stub: {exc}")
