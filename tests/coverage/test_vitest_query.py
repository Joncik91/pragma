"""Tests for query_vitest_coverage.

Builds fake V8 coverage-final.json files and asserts on the returned dict.
No Node or vitest required.
"""

from __future__ import annotations

import json
from pathlib import Path

from pragma.coverage.query import query_vitest_coverage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _v8_entry(target_path: str, statements: dict[str, dict], hits: dict[str, int]) -> dict:
    """Build a minimal V8 coverage entry for `target_path`."""
    return {
        target_path: {
            "path": target_path,
            "statementMap": statements,
            "s": hits,
            "fnMap": {},
            "f": {},
            "branchMap": {},
            "b": {},
        }
    }


def _stmt(start_line: int, end_line: int | None = None) -> dict:
    """Build a statementMap entry for the given line range."""
    end_line = end_line if end_line is not None else start_line
    return {
        "start": {"line": start_line, "column": 0},
        "end": {"line": end_line, "column": 40},
    }


def _write_report(tmp_path: Path, data: dict, name: str = "coverage-final.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return p


# ---------------------------------------------------------------------------
# Failure / missing-data paths → {} or None sentinel
# ---------------------------------------------------------------------------


def test_query_vitest_returns_empty_when_json_missing(tmp_path: Path) -> None:
    """coverage_json path does not exist → {}."""
    result = query_vitest_coverage(tmp_path / "nope.json", tmp_path / "x.ts", range(1, 10))
    assert result == {}


def test_query_vitest_returns_empty_when_json_malformed(tmp_path: Path) -> None:
    """coverage_json is not valid JSON → {}."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{{")
    result = query_vitest_coverage(bad, tmp_path / "x.ts", range(1, 10))
    assert result == {}


def test_query_vitest_returns_empty_when_target_absent_from_report(tmp_path: Path) -> None:
    """JSON has entries for other files but not target_file → {}."""
    other = str(tmp_path / "other.ts")
    data = _v8_entry(other, {"0": _stmt(5)}, {"0": 3})
    report = _write_report(tmp_path, data)
    target = tmp_path / "missing.ts"
    result = query_vitest_coverage(report, target, range(1, 10))
    assert result == {}


# ---------------------------------------------------------------------------
# Aggregate-true: at least one target line was hit
# ---------------------------------------------------------------------------


def test_query_vitest_returns_aggregate_true_when_target_lines_hit(tmp_path: Path) -> None:
    """statementMap line 7 hit > 0 and target_lines includes 7 → {"_aggregate": True}."""
    target = tmp_path / "foo.ts"
    target.write_text("// stub\n")
    data = _v8_entry(
        str(target),
        {"0": _stmt(3), "1": _stmt(7), "2": _stmt(9)},
        {"0": 0, "1": 2, "2": 0},
    )
    report = _write_report(tmp_path, data)
    result = query_vitest_coverage(report, target, range(5, 10))
    assert result == {"_aggregate": True}


def test_query_vitest_aggregate_true_when_first_line_in_range_hit(tmp_path: Path) -> None:
    """First line of the range has a hit → True."""
    target = tmp_path / "bar.ts"
    target.write_text("// stub\n")
    data = _v8_entry(
        str(target),
        {"0": _stmt(1), "1": _stmt(5), "2": _stmt(10)},
        {"0": 1, "1": 0, "2": 0},
    )
    report = _write_report(tmp_path, data)
    result = query_vitest_coverage(report, target, range(1, 4))
    assert result == {"_aggregate": True}


# ---------------------------------------------------------------------------
# Aggregate-false: target file present but no lines in range hit
# ---------------------------------------------------------------------------


def test_query_vitest_returns_aggregate_false_when_target_lines_unhit(tmp_path: Path) -> None:
    """All statements in target_lines have 0 hits → {"_aggregate": False}."""
    target = tmp_path / "foo.ts"
    target.write_text("// stub\n")
    data = _v8_entry(
        str(target),
        {"0": _stmt(5), "1": _stmt(6), "2": _stmt(7)},
        {"0": 0, "1": 0, "2": 0},
    )
    report = _write_report(tmp_path, data)
    result = query_vitest_coverage(report, target, range(5, 8))
    assert result == {"_aggregate": False}


def test_query_vitest_aggregate_false_when_only_out_of_range_lines_hit(tmp_path: Path) -> None:
    """Lines outside target_lines are hit, but none inside range → False."""
    target = tmp_path / "baz.ts"
    target.write_text("// stub\n")
    data = _v8_entry(
        str(target),
        {"0": _stmt(2), "1": _stmt(20), "2": _stmt(50)},
        {"0": 5, "1": 3, "2": 7},
    )
    report = _write_report(tmp_path, data)
    # range(10, 15) — none of lines 2, 20, 50 fall in this range
    result = query_vitest_coverage(report, target, range(10, 15))
    assert result == {"_aggregate": False}


def test_query_vitest_returns_aggregate_false_when_no_statements_in_report(tmp_path: Path) -> None:
    """target_file is in the report but statementMap is empty → False."""
    target = tmp_path / "empty.ts"
    target.write_text("// stub\n")
    data = _v8_entry(str(target), {}, {})
    report = _write_report(tmp_path, data)
    result = query_vitest_coverage(report, target, range(1, 10))
    assert result == {"_aggregate": False}


# ---------------------------------------------------------------------------
# Path resolution: relative-path keys in JSON should resolve correctly
# ---------------------------------------------------------------------------


def test_query_vitest_handles_relative_path_keys(tmp_path: Path) -> None:
    """JSON key is a relative path that resolves to target_file → matched."""
    target = tmp_path / "src" / "utils.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// stub\n")

    # Construct a key like /tmp/pytest-xxx/./src/utils.ts — still resolves same.
    parent_str = str(target.parent.resolve())
    relative_key = parent_str + "/." + "/" + target.name  # e.g. /tmp/.../src/./utils.ts

    data = _v8_entry(
        relative_key,
        {"0": _stmt(3), "1": _stmt(5)},
        {"0": 4, "1": 0},
    )
    report = _write_report(tmp_path, data)
    result = query_vitest_coverage(report, target, range(3, 6))
    assert result == {"_aggregate": True}
