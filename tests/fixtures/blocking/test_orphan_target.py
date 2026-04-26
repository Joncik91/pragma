"""Fixture: test_orphan_target.py never imports `orphan_target`; redefines class inline.

Triggers `python.orphan_test`.
"""


class OrphanTarget:
    def __init__(self) -> None:
        self.value = 42


def test_orphan_target_basic():
    o = OrphanTarget()
    assert o.value == 42
