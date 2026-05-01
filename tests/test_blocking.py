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


def test_python_xfail_gaming_is_blocking():
    assert is_blocking_kind("python.xfail_gaming") is True


def test_python_module_shimmed_is_blocking():
    assert is_blocking_kind("python.module_shimmed") is True


def test_python_module_attr_reassignment_is_blocking():
    assert is_blocking_kind("python.module_attr_reassignment") is True


def test_vitest_orphan_mock_is_blocking():
    assert is_blocking_kind("vitest.orphan_mock") is True


def test_python_orphan_test_is_blocking():
    assert is_blocking_kind("python.orphan_test") is True


def test_blocking_suffixes_includes_all_sixteen():
    assert (
        frozenset(
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
        == BLOCKING_SUFFIXES
    )


def test_jest_test_failing_gaming_is_blocking():
    assert is_blocking_kind("jest.test_failing_gaming") is True


def test_python_no_success_assertion_is_blocking():
    assert is_blocking_kind("python.no_success_assertion") is True


def test_vitest_no_success_assertion_is_blocking():
    assert is_blocking_kind("vitest.no_success_assertion") is True


def test_python_target_not_covered_is_blocking():
    assert is_blocking_kind("python.target_not_covered") is True


def test_vitest_target_not_covered_is_blocking():
    assert is_blocking_kind("vitest.target_not_covered") is True


def test_vitest_stub_error_match_is_blocking():
    assert is_blocking_kind("vitest.stub_error_match") is True
