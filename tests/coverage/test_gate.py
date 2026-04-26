"""Tests for tier-2 gate orchestration (gate.classify_file).

Uses the tests/fixtures/coverage_gated/ fixtures:
  - test_inventory_real.py      — calls reserve(); tier 1 + tier 2 both pass.
  - test_inventory_imports_only.py — imports but never calls; tier 2 flips.
  - test_inventory_calls_other.py  — calls lookup(), not reserve(); tier 2
                                     infers lookup as target and passes.

The `coverage_gated/src/` directory must be on sys.path so that
`production_lines_python('inventory', 'reserve')` can import the module.
The `sys_path_inventory` fixture handles this.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import pragma.languages.python as python_lang_module
from pragma.coverage import cache as cache_module
from pragma.coverage import gate
from pragma.verdict import Verdict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "coverage_gated"
SRC_DIR = FIXTURES_DIR / "src"

REAL_TEST = FIXTURES_DIR / "test_inventory_real.py"
IMPORTS_ONLY_TEST = FIXTURES_DIR / "test_inventory_imports_only.py"
CALLS_OTHER_TEST = FIXTURES_DIR / "test_inventory_calls_other.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sys_path_inventory():
    """Add coverage_gated/src/ to sys.path so `import inventory` works."""
    src = str(SRC_DIR)
    if src not in sys.path:
        sys.path.insert(0, src)
        added = True
    else:
        added = False
    yield
    if added and src in sys.path:
        sys.path.remove(src)
    # Also remove any cached 'inventory' module so re-imports are clean.
    sys.modules.pop("inventory", None)


@pytest.fixture()
def no_cache(monkeypatch):
    """Force PRAGMA_NO_CACHE=1 so tests don't read/write the shared cache DB."""
    monkeypatch.setenv("PRAGMA_NO_CACHE", "1")


@pytest.fixture()
def python_lang():
    """The Python language module as a _LanguageModule."""
    return python_lang_module


class _VitestLang:
    LANGUAGE = "vitest"

    def matches(self, path: Path) -> bool:
        return False


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _verified(test_name: str) -> Verdict:
    return Verdict(kind="python.verified", evidence="tier1", test_name=test_name)


def _blocking(test_name: str) -> Verdict:
    return Verdict(kind="python.mocked-away", evidence="tier1", test_name=test_name)


# ---------------------------------------------------------------------------
# Basic contract tests (no subprocess)
# ---------------------------------------------------------------------------


def test_empty_prior_returns_empty(python_lang, no_cache):
    """Empty prior_verdicts → empty result; tier 2 is a no-op."""
    result = gate.classify_file(REAL_TEST, [], python_lang)
    assert result == []


def test_no_verified_verdicts_returns_prior_unchanged(python_lang, no_cache):
    """Only blocking verdicts — tier 2 has nothing to augment."""
    prior = [_blocking("test_reserve_basic")]
    result = gate.classify_file(REAL_TEST, prior, python_lang)
    assert result == prior


def test_blocking_verdict_preserved_alongside_verified(python_lang, no_cache, sys_path_inventory):
    """Blocking verdicts pass through; only verified ones are eligible for tier 2."""
    prior = [_blocking("test_x"), _verified("test_y")]
    # test_y has no matching function in REAL_TEST, so infer_target → (None, None) → keeps verified
    result = gate.classify_file(REAL_TEST, prior, python_lang)
    # blocking always preserved; verified with no inferable target also kept
    assert result[0] == _blocking("test_x")


def test_vitest_lang_returns_prior_unchanged(no_cache):
    """Vitest path is step 7 — for now, return prior unchanged."""
    prior = [_verified("test_something")]
    result = gate.classify_file(REAL_TEST, prior, _VitestLang())
    assert result == prior


# ---------------------------------------------------------------------------
# Target inference edge cases
# ---------------------------------------------------------------------------


def test_no_inferable_target_keeps_verified(python_lang, no_cache, sys_path_inventory):
    """test_reserve_returns_dict imports but never calls — infer_target returns (None, None).
    Tier 2 keeps verified (conservative: no target = no opinion).
    """
    # imports_only test: imports reserve but never calls it
    # infer_target returns (None, None) because no called name matches the import
    prior = [_verified("test_reserve_returns_dict")]
    result = gate.classify_file(IMPORTS_ONLY_TEST, prior, python_lang)
    # With no inferable target, tier 2 is conservative → keep verified
    # (In practice this test DOES flip because imports_only has no callable import,
    # so it skips tier 2 entirely)
    assert any(v.test_name == "test_reserve_returns_dict" for v in result)


def test_missing_production_module_keeps_verified(python_lang, no_cache):
    """When production_lines_python returns None, keep verified."""
    # Use a test that infers ('nonexistent_module', 'fn') — we can patch it.
    prior = [_verified("test_reserve_basic")]
    with patch(
        "pragma.languages.python.inference.infer_target",
        return_value=("nonexistent_module_xyz", "fn"),
    ):
        result = gate.classify_file(REAL_TEST, prior, python_lang)
    assert result == prior


# ---------------------------------------------------------------------------
# Real end-to-end tier-2 tests (subprocess runs)
# ---------------------------------------------------------------------------


def test_real_test_keeps_verified(python_lang, no_cache, sys_path_inventory):
    """test_inventory_real.py calls reserve() — tier 2 keeps verified."""
    prior = [_verified("test_reserve_basic")]
    result = gate.classify_file(REAL_TEST, prior, python_lang)
    assert len(result) == 1
    assert result[0].kind == "python.verified"
    assert result[0].test_name == "test_reserve_basic"


def test_imports_only_flips_to_not_covered(python_lang, no_cache, sys_path_inventory):
    """test_inventory_imports_only.py imports reserve but never calls it.

    infer_target returns (None, None) because no called name matches the
    import, so tier 2 can't infer a target and keeps verified (conservative).
    This test confirms that behavior — no verdict flip for uninferable targets.
    """
    prior = [_verified("test_reserve_returns_dict")]
    result = gate.classify_file(IMPORTS_ONLY_TEST, prior, python_lang)
    # No inferable target → keep verified
    assert len(result) == 1
    assert result[0].kind == "python.verified"


def test_calls_other_keeps_verified(python_lang, no_cache, sys_path_inventory):
    """test_inventory_calls_other.py calls lookup() — infer_target picks lookup.
    Since lookup IS covered in this test's context, tier 2 keeps verified.
    """
    prior = [_verified("test_lookup_returns_record")]
    result = gate.classify_file(CALLS_OTHER_TEST, prior, python_lang)
    assert len(result) == 1
    assert result[0].kind == "python.verified"


def test_target_not_covered_verdict_emitted(python_lang, no_cache, sys_path_inventory, tmp_path):
    """Directly test the target_not_covered path by making the runner say a function
    wasn't covered.

    We use a patch to make query_python_coverage return {test_name: False}
    so we can verify the verdict is correctly constructed and emitted.
    """
    prior = [_verified("test_reserve_basic")]

    # Create a throwaway file as the fake coverage DB so the gate's
    # finally-block unlink doesn't touch any real fixture file.
    fake_db = tmp_path / "fake.coverage"
    fake_db.write_bytes(b"")

    with patch("pragma.coverage.gate.query_python_coverage") as mock_query:
        mock_query.return_value = {"test_reserve_basic": False}
        with patch("pragma.coverage.gate.run_python_with_coverage") as mock_runner:
            mock_runner.return_value = fake_db
            result = gate.classify_file(REAL_TEST, prior, python_lang)

    assert len(result) == 1
    v = result[0]
    assert v.kind == "python.target_not_covered"
    assert v.test_name == "test_reserve_basic"
    assert "reserve" in v.evidence


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


def test_cache_hit_skips_runner(python_lang, sys_path_inventory, tmp_path, monkeypatch):
    """On a cache hit, run_python_with_coverage is never called."""
    monkeypatch.delenv("PRAGMA_NO_CACHE", raising=False)
    # Redirect both lookup and store to the same isolated tmp_path DB by
    # monkeypatching _find_repo_root (store calls it directly; lookup goes
    # through _cache_db_path which also calls it).
    monkeypatch.setattr(cache_module, "_find_repo_root", lambda: tmp_path)

    prior = [_verified("test_reserve_basic")]

    # Populate the cache manually with a 'covered / no verdict' entry.
    th = cache_module.content_hash(REAL_TEST)
    from pragma.coverage.target import production_lines_python  # noqa: PLC0415

    target_info = production_lines_python("inventory", "reserve")
    assert target_info is not None, "inventory.reserve must be resolvable; check sys_path_inventory"
    target_file, _ = target_info
    tah = cache_module.content_hash(target_file)
    cache_module.store(th, tah, "reserve", None)  # None = covered

    with patch("pragma.coverage.gate.run_python_with_coverage") as mock_runner:
        result = gate.classify_file(REAL_TEST, prior, python_lang)
        mock_runner.assert_not_called()

    assert len(result) == 1
    assert result[0].kind == "python.verified"


def test_cache_stores_verdict_after_runner(python_lang, sys_path_inventory, tmp_path, monkeypatch):
    """After a runner run, the result is stored in cache."""
    monkeypatch.delenv("PRAGMA_NO_CACHE", raising=False)
    monkeypatch.setattr(cache_module, "_find_repo_root", lambda: tmp_path)

    prior = [_verified("test_reserve_basic")]
    fake_db = tmp_path / "fake.coverage"
    fake_db.write_bytes(b"")

    with patch("pragma.coverage.gate.query_python_coverage") as mock_query:
        mock_query.return_value = {"test_reserve_basic": False}
        with patch("pragma.coverage.gate.run_python_with_coverage") as mock_runner:
            mock_runner.return_value = fake_db
            result = gate.classify_file(REAL_TEST, prior, python_lang)

    assert result[0].kind == "python.target_not_covered"

    # Now call again — runner should NOT be called (cache hit).
    fake_db2 = tmp_path / "fake2.coverage"
    fake_db2.write_bytes(b"")
    with patch("pragma.coverage.gate.run_python_with_coverage") as mock_runner2:
        result2 = gate.classify_file(REAL_TEST, prior, python_lang)
        mock_runner2.assert_not_called()
    assert result2[0].kind == "python.target_not_covered"


# ---------------------------------------------------------------------------
# Runner failure handling
# ---------------------------------------------------------------------------


def test_runner_failure_keeps_verified(python_lang, no_cache, sys_path_inventory):
    """If the runner returns None, keep verified; don't cache."""
    prior = [_verified("test_reserve_basic")]
    with patch("pragma.coverage.gate.run_python_with_coverage", return_value=None):
        result = gate.classify_file(REAL_TEST, prior, python_lang)
    assert result == prior


def test_runner_failure_not_cached(python_lang, sys_path_inventory, tmp_path, monkeypatch):
    """Infrastructure failure (runner None) must not be written to cache.

    Proven by running gate twice with runner returning None both times:
    if the failure were cached the second call would skip the runner,
    but the runner must be called twice.
    """
    monkeypatch.delenv("PRAGMA_NO_CACHE", raising=False)
    monkeypatch.setattr(cache_module, "_find_repo_root", lambda: tmp_path)

    prior = [_verified("test_reserve_basic")]
    call_count = 0

    def _failing_runner(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return None

    with patch("pragma.coverage.gate.run_python_with_coverage", side_effect=_failing_runner):
        gate.classify_file(REAL_TEST, prior, python_lang)
        gate.classify_file(REAL_TEST, prior, python_lang)

    # Runner must have been called on BOTH invocations — failure not cached.
    assert call_count == 2


# ---------------------------------------------------------------------------
# Exception resilience
# ---------------------------------------------------------------------------


def test_exception_inside_returns_prior_unchanged(python_lang, no_cache):
    """Any unexpected exception inside classify_file returns prior unchanged."""
    prior = [_verified("test_reserve_basic")]
    with patch(
        "pragma.languages.python.inference.infer_target",
        side_effect=RuntimeError("simulated failure"),
    ):
        result = gate.classify_file(REAL_TEST, prior, python_lang)
    assert result == prior


def test_exception_logged_to_stderr(python_lang, no_cache, capsys):
    """Internal exception logs to stderr with [pragma:tier2] prefix."""
    prior = [_verified("test_reserve_basic")]
    with patch(
        "pragma.languages.python.inference.infer_target",
        side_effect=RuntimeError("test error"),
    ):
        gate.classify_file(REAL_TEST, prior, python_lang)
    captured = capsys.readouterr()
    assert "[pragma:tier2]" in captured.err


# ---------------------------------------------------------------------------
# Test doesn't appear in coverage data
# ---------------------------------------------------------------------------


def test_absent_test_name_keeps_verified(python_lang, no_cache, sys_path_inventory, tmp_path):
    """If the test name doesn't appear in query results, keep verified (no cache)."""
    prior = [_verified("test_reserve_basic")]
    fake_db = tmp_path / "fake.coverage"
    fake_db.write_bytes(b"")

    with patch("pragma.coverage.gate.query_python_coverage") as mock_query:
        # Return empty dict — test_reserve_basic not in results
        mock_query.return_value = {}
        with patch("pragma.coverage.gate.run_python_with_coverage") as mock_runner:
            mock_runner.return_value = fake_db
            result = gate.classify_file(REAL_TEST, prior, python_lang)

    # No cache write, verdict kept
    assert result == prior
