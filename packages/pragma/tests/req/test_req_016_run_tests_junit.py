"""Red tests for REQ-016 - run_tests emits junit.xml by default.

BUG-020: `run_tests` passes `-o addopts=` (BUG-015 fix), which also
strips any `--junit-xml=` the user declared in addopts. Pragma's own
internal flows (`slice complete`, `unlock`, `verify gate`) finish
without writing `.pragma/pytest-junit.xml`, so the PIL aggregator
shows "missing" for every permutation on a fresh greenfield project
even when the user followed the docs. Fix: run_tests emits junit
explicitly via `--junit-xml=<path>` so it survives the addopts clear,
defaulting to `<cwd>/.pragma/pytest-junit.xml` which is where the
aggregator looks.
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
            """
        ),
        encoding="utf-8",
    )
    return tests_dir


@trace("REQ-016")
def _assert_run_tests_writes_junit_xml(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    default_junit = pragma_dir / "pytest-junit.xml"
    assert not default_junit.exists()
    collected = collect_tests(tests_dir, cwd=tmp_path)
    by_name = {c.name: c for c in collected}
    results = run_tests(tests_dir, nodeids=[by_name["test_req_001_green"].nodeid], cwd=tmp_path)
    assert results[by_name["test_req_001_green"].nodeid] == "passed"
    assert default_junit.exists(), (
        f"run_tests must emit junit.xml at the default path "
        f"({default_junit}); the PIL aggregator looks there."
    )
    assert default_junit.stat().st_size > 0, "junit.xml must not be empty"


@trace("REQ-016")
def _assert_run_tests_honours_explicit_junit_path(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    junit_path = tmp_path / "custom" / "report.xml"
    collected = collect_tests(tests_dir, cwd=tmp_path)
    by_name = {c.name: c for c in collected}
    results = run_tests(
        tests_dir,
        nodeids=[by_name["test_req_001_green"].nodeid],
        cwd=tmp_path,
        junit_xml=junit_path,
    )
    assert results[by_name["test_req_001_green"].nodeid] == "passed"
    assert junit_path.exists(), (
        f"run_tests must honour an explicit junit_xml parameter ({junit_path})"
    )


@trace("REQ-016")
def _assert_run_tests_junit_survives_addopts_q(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q"\n',
        encoding="utf-8",
    )
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    default_junit = pragma_dir / "pytest-junit.xml"
    collected = collect_tests(tests_dir, cwd=tmp_path)
    by_name = {c.name: c for c in collected}
    results = run_tests(tests_dir, nodeids=[by_name["test_req_001_green"].nodeid], cwd=tmp_path)
    # Verdict still correct (BUG-015 fix holds):
    assert results[by_name["test_req_001_green"].nodeid] == "passed"
    # And junit.xml still written (BUG-020 fix):
    assert default_junit.exists(), (
        "run_tests must emit junit.xml even when a parent pytest.ini "
        "pins -q in addopts; the BUG-015 addopts-clear must not strip "
        "the junit directive too."
    )


def test_req_016_run_tests_writes_junit_xml(tmp_path: Path) -> None:
    with set_permutation("run_tests_writes_junit_xml"):
        _assert_run_tests_writes_junit_xml(tmp_path)


def test_req_016_run_tests_honours_explicit_junit_path(tmp_path: Path) -> None:
    with set_permutation("run_tests_honours_explicit_junit_path"):
        _assert_run_tests_honours_explicit_junit_path(tmp_path)


def test_req_016_run_tests_junit_survives_addopts_q(tmp_path: Path) -> None:
    with set_permutation("run_tests_junit_survives_addopts_q"):
        _assert_run_tests_junit_survives_addopts_q(tmp_path)
