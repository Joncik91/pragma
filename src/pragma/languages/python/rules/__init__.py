"""Ordered list of Python rules. Each rule is a callable

    classify(func, *, test_name, expected, target_module, target_symbol) -> Verdict | None

The orchestrator (Task 7) walks RULES and returns the first non-None verdict;
falls back to `python.verified` when every rule returns None.

Order matters — first match wins. Mirrors v1.1.0's _classify_in_order priority.
"""

from __future__ import annotations

from collections.abc import Callable

from pragma.languages.python.rules import conditional as _conditional
from pragma.languages.python.rules import empty_body as _empty_body
from pragma.languages.python.rules import mismatched as _mismatched
from pragma.languages.python.rules import mocked_away as _mocked_away
from pragma.languages.python.rules import module_attr_reassignment as _module_attr_reassignment
from pragma.languages.python.rules import module_shimmed as _module_shimmed
from pragma.languages.python.rules import monkeypatched as _monkeypatched
from pragma.languages.python.rules import orphan_test as _orphan_test
from pragma.languages.python.rules import parametrize_thin as _parametrize_thin
from pragma.languages.python.rules import skipped as _skipped
from pragma.languages.python.rules import swallowed as _swallowed
from pragma.languages.python.rules import tautological as _tautological
from pragma.languages.python.rules import verified_fallback as _verified_fallback
from pragma.languages.python.rules import weak as _weak
from pragma.languages.python.rules import xfail_gaming as _xfail_gaming

RULES: list[Callable] = [
    _mocked_away.classify,
    _monkeypatched.classify,
    _module_attr_reassignment.classify,
    _module_shimmed.classify,
    _swallowed.classify,
    _skipped.classify,
    _xfail_gaming.classify,
    _mismatched.classify,
    _conditional.classify,
    _tautological.classify,
    _empty_body.classify,
    _parametrize_thin.classify,
    _weak.classify,
    _orphan_test.classify,
    _verified_fallback.classify,
]
