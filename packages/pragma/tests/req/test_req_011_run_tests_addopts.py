"""Red tests for REQ-011 - run_tests overrides inherited addopts.

BUG-015: a parent pytest.ini / pyproject with `addopts = -q` compresses
pytest per-test output from `path::name PASSED/FAILED` lines down to
`.`/`F` dots, which makes run_tests's output regex match zero lines
and report every test as `error` even when it passes. collect_tests
already fixes this by passing `-o addopts=` (v1.0.3, BUG-009/KI-12);
run_tests must do the same.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.core.tests_discovery import collect_tests, run_tests


def _write_tests_tree(tmp_path: Path) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent(
            """
            def test_req_001_green():
                assert True

            def test_req_001_red():
                assert False
            """
        ),
        encoding="utf-8",
    )
    return tests_dir


@trace("REQ-011")
def _assert_runs_under_parent_addopts_q(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q"\n',
        encoding="utf-8",
    )
    collected = collect_tests(tests_dir)
    by_name = {c.name: c for c in collected}
    results = run_tests(
        tests_dir,
        nodeids=[by_name["test_req_001_green"].nodeid, by_name["test_req_001_red"].nodeid],
    )
    assert results[by_name["test_req_001_green"].nodeid] == "passed", (
        f"run_tests must see the green test as passed even with -q in addopts; got {results!r}"
    )
    assert results[by_name["test_req_001_red"].nodeid] == "failed", (
        f"run_tests must see the red test as failed even with -q in addopts; got {results!r}"
    )


@trace("REQ-011")
def _assert_runs_from_clean_dir(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    collected = collect_tests(tests_dir)
    by_name = {c.name: c for c in collected}
    results = run_tests(
        tests_dir,
        nodeids=[by_name["test_req_001_green"].nodeid, by_name["test_req_001_red"].nodeid],
    )
    assert results[by_name["test_req_001_green"].nodeid] == "passed"
    assert results[by_name["test_req_001_red"].nodeid] == "failed"


def test_req_011_runs_under_parent_addopts_q(tmp_path: Path) -> None:
    with set_permutation("runs_under_parent_addopts_q"):
        _assert_runs_under_parent_addopts_q(tmp_path)


def test_req_011_runs_from_clean_dir(tmp_path: Path) -> None:
    with set_permutation("runs_from_clean_dir"):
        _assert_runs_from_clean_dir(tmp_path)
