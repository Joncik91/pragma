"""Production module under test by tests/fixtures/coverage_gated/test_*.py.

Placeholder for v2.1.0 step 1 — content stabilizes in step 5 once the
gate is wired. Tier 2 fixture pattern: real production code lives
alongside the gamed/honest test variants so coverage instrumentation
can attribute hits per-test.
"""

from __future__ import annotations


def reserve(sku: str, qty: int) -> dict[str, str | int | bool]:
    """Reserve `qty` of `sku`; returns the reservation record."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    return {"sku": sku, "qty": qty, "reserved": True}


def lookup(sku: str) -> dict[str, str | int]:
    """Find a SKU; returns a stub record. Used by tests that exercise the
    'wrong symbol' gaming variant (test imports inventory but only calls
    lookup, never reserve)."""
    return {"sku": sku, "in_stock": 0}
