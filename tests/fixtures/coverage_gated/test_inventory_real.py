"""Honest fixture: imports + calls + asserts on `reserve`. Tier 1 + Tier 2 should both pass."""

from __future__ import annotations

from inventory import reserve


def test_reserve_basic() -> None:
    result = reserve("SKU-1", 5)
    assert result["sku"] == "SKU-1"
    assert result["qty"] == 5
    assert result["reserved"] is True
