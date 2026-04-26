"""Gamed fixture: imports `reserve` (the inferred target) but only calls `lookup`.

Tier 1 sees `reserve` imported and `lookup` called; can't tell which is
the production target. Returns `python.verified`. Tier 2 catches it:
`reserve`'s lines have zero hits in this test's coverage context, even
though SOME `inventory` lines did run.
"""

from __future__ import annotations

from inventory import lookup, reserve  # noqa: F401


def test_lookup_returns_record() -> None:
    record = lookup("SKU-1")
    assert record["sku"] == "SKU-1"
