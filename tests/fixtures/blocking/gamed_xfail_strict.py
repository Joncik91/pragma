"""Fixture: pytest.mark.xfail(strict=True) lets stubs ship green.

Triggers `python.xfail_gaming`.
"""

import pytest


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="stub")
def test_discount_applies_percentage():
    import pricing  # type: ignore[import-not-found]
    assert pricing.discount(100.0, "SAVE10") == 90.0


@pytest.mark.xfail(strict=True)
def test_discount_floors_at_zero():
    import pricing  # type: ignore[import-not-found]
    assert pricing.discount(0.0, "SAVE10") == 0.0
