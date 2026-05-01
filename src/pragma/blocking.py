"""Single source of truth for which verdict suffixes block an edit."""

from __future__ import annotations

BLOCKING_SUFFIXES: frozenset[str] = frozenset(
    {
        "tautological",
        "mocked-away",
        "monkeypatched",
        "module_attr_reassignment",
        "module_shimmed",
        "orphan_mock",
        "orphan_test",
        "swallowed",
        "skipped",
        "xfail_gaming",
        "conditional",
        "mismatched",
        "stub_error_match",
        "no_success_assertion",
        "test_failing_gaming",
        "target_not_covered",
    }
)


def is_blocking_kind(kind: str) -> bool:
    """True when `kind` is a blocking verdict.

    Accepts either a language-prefixed kind (`python.tautological`) or a
    bare suffix (`tautological`). Bare suffixes are supported so the bash
    hook can still operate when it pulls the suffix list as JSON.
    """
    suffix = kind.rsplit(".", 1)[-1]
    return suffix in BLOCKING_SUFFIXES
