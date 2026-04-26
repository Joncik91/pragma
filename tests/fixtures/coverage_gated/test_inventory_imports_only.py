"""Gamed fixture: imports `reserve` but the test body never calls it.

Tier 1 sees a clean assertion shape and returns `python.verified`.
Tier 2 (when enabled) runs the test under coverage, sees zero hits on
`reserve`'s lines for this test's context, and emits
`python.target_not_covered`.
"""

from __future__ import annotations

from inventory import reserve  # noqa: F401


def test_reserve_returns_dict() -> None:
    # Note: never calls reserve(). Asserts on a literal that happens to
    # match what reserve() would return, but the production code is
    # never exercised — classic orphan-test gaming.
    fake_record = {"sku": "SKU-1", "qty": 5, "reserved": True}
    assert fake_record["reserved"] is True
