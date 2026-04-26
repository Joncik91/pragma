"""Fixture: sys.modules["X"] = stub replaces the production module.

Triggers `python.module_shimmed`.
"""

import sys
import types

_mod = types.ModuleType("orders")
_mod.create_order = lambda items, customer_id: {"order_id": "ord-001"}
sys.modules["orders"] = _mod

import orders  # type: ignore[import-not-found]


def test_create_order_returns_dict():
    result = orders.create_order([{"sku": "A"}], "c-1")
    assert isinstance(result, dict)
