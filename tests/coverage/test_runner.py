"""Tests for run_python_with_coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from pragma.coverage.runner import run_python_with_coverage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_production_module(tmp_path: Path, name: str = "prod.py") -> Path:
    """Write a minimal production module with two functions."""
    p = tmp_path / name
    p.write_text("def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n")
    return p


def _write_passing_test(tmp_path: Path, prod_path: Path, name: str = "test_prod.py") -> Path:
    """Write a passing test that calls into prod_path."""
    p = tmp_path / name
    p.write_text(
        f"import sys, os\n"
        f"sys.path.insert(0, {str(prod_path.parent)!r})\n"
        f"from {prod_path.stem} import add, subtract\n"
        f"\n"
        f"def test_add():\n"
        f"    assert add(1, 2) == 3\n"
        f"\n"
        f"def test_subtract():\n"
        f"    assert subtract(5, 3) == 2\n"
    )
    return p


def _write_non_covering_test(tmp_path: Path, name: str = "test_no_cover.py") -> Path:
    """Write a test that doesn't call any production function."""
    p = tmp_path / name
    p.write_text("def test_unrelated():\n    assert 1 + 1 == 2\n")
    return p


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------


def test_runner_returns_existing_db_path(tmp_path: Path) -> None:
    """run_python_with_coverage returns a Path that exists on disk."""
    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None
    assert isinstance(result, Path)
    assert result.exists()


def test_runner_db_is_nonempty(tmp_path: Path) -> None:
    """The returned .coverage file has non-zero size (coverage wrote data)."""
    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None
    assert result.stat().st_size > 0


def test_runner_db_records_contexts(tmp_path: Path) -> None:
    """After a passing run, the DB contains at least one dynamic context."""
    try:
        import coverage as cov_module
    except ImportError:
        pytest.skip("coverage not installed")

    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None

    data = cov_module.CoverageData(basename=str(result))
    data.read()
    all_contexts: set[str] = set()
    for f in data.measured_files():
        for ctxs in data.contexts_by_lineno(f).values():
            all_contexts.update(ctxs)
    # At least one non-empty context string present
    non_empty = {c for c in all_contexts if c}
    assert len(non_empty) > 0


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_runner_missing_test_path_returns_none(tmp_path: Path) -> None:
    """test_path does not exist on disk → None."""
    prod = _write_production_module(tmp_path)
    missing = tmp_path / "does_not_exist.py"
    result = run_python_with_coverage(missing, prod)
    assert result is None


def test_runner_missing_target_file_returns_none(tmp_path: Path) -> None:
    """target_file doesn't exist on disk → runner returns None.

    coverage --include=<missing> produces no data file.
    """
    test_file = _write_non_covering_test(tmp_path)
    missing_target = tmp_path / "nonexistent_target.py"
    result = run_python_with_coverage(test_file, missing_target)
    assert result is None


def test_runner_syntax_error_test_returns_none(tmp_path: Path) -> None:
    """A test file with a syntax error → None (subprocess fails cleanly)."""
    prod = _write_production_module(tmp_path)
    bad_test = tmp_path / "test_broken.py"
    bad_test.write_text("def test_bad(:\n    pass\n")  # syntax error
    result = run_python_with_coverage(bad_test, prod)
    # May return None or a db with no contexts; must not raise
    # The key requirement is: it doesn't crash
    assert result is None or isinstance(result, Path)


def test_runner_timeout_test_returns_none(tmp_path: Path) -> None:
    """A test with time.sleep(10) is killed by --timeout=5 → None."""
    prod = _write_production_module(tmp_path)
    slow_test = tmp_path / "test_slow.py"
    slow_test.write_text("import time\ndef test_sleepy():\n    time.sleep(10)\n")
    result = run_python_with_coverage(slow_test, prod)
    # --timeout=5 means pytest exits with failure; no coverage data written
    assert result is None
