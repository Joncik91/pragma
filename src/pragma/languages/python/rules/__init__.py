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
from pragma.languages.python.rules import monkeypatched as _monkeypatched
from pragma.languages.python.rules import parametrize_thin as _parametrize_thin
from pragma.languages.python.rules import skipped as _skipped
from pragma.languages.python.rules import swallowed as _swallowed
from pragma.languages.python.rules import tautological as _tautological
from pragma.languages.python.rules import verified_fallback as _verified_fallback
from pragma.languages.python.rules import weak as _weak

RULES: list[Callable] = [
    _mocked_away.classify,
    _monkeypatched.classify,
    _swallowed.classify,
    _skipped.classify,
    _mismatched.classify,
    _conditional.classify,
    _tautological.classify,
    _empty_body.classify,
    _parametrize_thin.classify,
    _weak.classify,
    _verified_fallback.classify,
]
