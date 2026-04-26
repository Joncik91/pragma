"""Fixture: top-level module-attribute reassignment swaps the production target.

Triggers `python.module_attr_reassignment`. Surfaced by v2.0.2 smoke
(py-monkey-attr sandbox).
"""

import pricing  # type: ignore[import-not-found]


def _real_discount(amount: float, code: str) -> float:
    return amount * 0.9


pricing.discount = _real_discount


def test_discount_applies_percentage():
    result = pricing.discount(100.0, "SAVE10")
    assert result == 90.0
