"""Tests for the single source of truth for blocking-verdict suffixes."""

from pragma.blocking import BLOCKING_SUFFIXES, is_blocking_kind


def test_python_tautological_is_blocking():
    assert is_blocking_kind("python.tautological") is True


def test_python_weak_is_not_blocking():
    assert is_blocking_kind("python.weak") is False


def test_vitest_skipped_is_blocking():
    assert is_blocking_kind("vitest.skipped") is True


def test_unknown_prefix_still_evaluates_suffix():
    assert is_blocking_kind("rust.tautological") is True
    assert is_blocking_kind("anything.empty_body") is False


def test_kind_without_dot_uses_whole_string():
    # Backwards compat: bare kind strings still work.
    assert is_blocking_kind("tautological") is True
    assert is_blocking_kind("verified") is False


def test_blocking_suffixes_includes_all_seven():
    assert (
        frozenset(
            {
                "tautological",
                "mocked-away",
                "monkeypatched",
                "swallowed",
                "skipped",
                "conditional",
                "mismatched",
            }
        )
        == BLOCKING_SUFFIXES
    )
