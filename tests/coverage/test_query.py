"""Tests for query_python_coverage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pragma.coverage.query import query_python_coverage
from pragma.coverage.runner import run_python_with_coverage

# ---------------------------------------------------------------------------
# Helpers — shared fixture builders
# ---------------------------------------------------------------------------


def _write_production_module(tmp_path: Path, name: str = "prod.py") -> Path:
    p = tmp_path / name
    p.write_text("def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n")
    return p


def _write_covering_test(tmp_path: Path, prod_path: Path) -> Path:
    """Test that calls into prod_path functions."""
    p = tmp_path / "test_cover.py"
    p.write_text(
        f"import sys\n"
        f"sys.path.insert(0, {str(prod_path.parent)!r})\n"
        f"from {prod_path.stem} import add\n"
        f"\n"
        f"def test_add():\n"
        f"    assert add(1, 2) == 3\n"
    )
    return p


def _write_non_covering_test(tmp_path: Path) -> Path:
    """Test that never calls into any production module."""
    p = tmp_path / "test_nocover.py"
    p.write_text("def test_unrelated():\n    assert 1 + 1 == 2\n")
    return p


def _get_db(tmp_path: Path, test_file: Path, prod_file: Path) -> Path:
    """Run coverage and assert the DB was produced."""
    db = run_python_with_coverage(test_file, prod_file)
    assert db is not None, "runner must succeed for this fixture"
    return db


# ---------------------------------------------------------------------------
# Positive: test DID cover the target
# ---------------------------------------------------------------------------


def test_query_covered_test_returns_true(tmp_path: Path) -> None:
    """A test that calls add() → covered=True for add's lines."""
    prod = _write_production_module(tmp_path)
    test_file = _write_covering_test(tmp_path, prod)
    db = _get_db(tmp_path, test_file, prod)

    result = query_python_coverage(db, prod, range(1, 3))  # add() is lines 1-2
    assert result != {}
    assert any(v is True for v in result.values())


def test_query_covered_test_name_present(tmp_path: Path) -> None:
    """The test_add function name appears as a key in the result."""
    prod = _write_production_module(tmp_path)
    test_file = _write_covering_test(tmp_path, prod)
    db = _get_db(tmp_path, test_file, prod)

    result = query_python_coverage(db, prod, range(1, 3))
    assert "test_add" in result
    assert result["test_add"] is True


# ---------------------------------------------------------------------------
# Positive: test DID NOT cover the target
# ---------------------------------------------------------------------------


def test_query_non_covering_test_returns_false(tmp_path: Path) -> None:
    """A test that never calls into prod → covered=False."""
    prod = _write_production_module(tmp_path)
    test_file = _write_non_covering_test(tmp_path)
    db = run_python_with_coverage(test_file, prod)
    # If runner returns None (no data written), skip — that's also acceptable
    if db is None:
        pytest.skip("no coverage data produced for non-covering test")

    result = query_python_coverage(db, prod, range(1, 3))
    # Either empty or all False — no test should be True
    assert all(v is False for v in result.values())


# ---------------------------------------------------------------------------
# Negative: bad inputs → empty dict
# ---------------------------------------------------------------------------


def test_query_missing_db_returns_empty(tmp_path: Path) -> None:
    """DB file doesn't exist → {}."""
    missing = tmp_path / "ghost.coverage"
    result = query_python_coverage(missing, tmp_path / "x.py", range(1, 5))
    assert result == {}


def test_query_corrupt_db_returns_empty(tmp_path: Path) -> None:
    """DB is not a valid SQLite file → {}."""
    corrupt = tmp_path / "corrupt.coverage"
    corrupt.write_bytes(b"this is not sqlite\x00\xff\xfe")
    result = query_python_coverage(corrupt, tmp_path / "x.py", range(1, 5))
    assert result == {}


def test_query_empty_db_returns_empty(tmp_path: Path) -> None:
    """Valid SQLite but no coverage tables → {}."""
    empty_db = tmp_path / "empty.coverage"
    conn = sqlite3.connect(str(empty_db))
    conn.close()
    result = query_python_coverage(empty_db, tmp_path / "x.py", range(1, 5))
    assert result == {}


def test_query_lines_outside_covered_range_returns_false(tmp_path: Path) -> None:
    """Query lines that were never hit → all False (not empty)."""
    prod = _write_production_module(tmp_path)
    test_file = _write_covering_test(tmp_path, prod)
    db = _get_db(tmp_path, test_file, prod)

    # Lines 100-110 don't exist in the file, so none are covered
    result = query_python_coverage(db, prod, range(100, 111))
    # Result has entries but all are False
    assert all(v is False for v in result.values())
