"""Ordered Vitest rules. First matching rule wins; fallback is `vitest.verified`."""

from __future__ import annotations

from collections.abc import Callable

from pragma.languages.vitest.rules import conditional as _conditional
from pragma.languages.vitest.rules import empty_body as _empty_body
from pragma.languages.vitest.rules import mismatched as _mismatched
from pragma.languages.vitest.rules import mocked_away as _mocked_away
from pragma.languages.vitest.rules import skipped as _skipped
from pragma.languages.vitest.rules import swallowed as _swallowed
from pragma.languages.vitest.rules import tautological as _tautological

RULES: list[Callable] = [
    _tautological.classify,
    _mocked_away.classify,
    _skipped.classify,
    _swallowed.classify,
    _empty_body.classify,
    _conditional.classify,
    _mismatched.classify,
]
