"""Red tests for REQ-014 - nested tests_root layouts.

BUG-018 (ex-KI-13): `run_tests` and `collect_tests` invoked pytest with
`cwd=tests_dir.parent`. For brownfield workspaces where the tests
directory is nested (Pragma's own `packages/pragma/tests/`), nodeids
came back relative to the user cwd but pytest was already chdir'd
below that, so nodeid lookup failed and every verdict was `error`.
v1.0.6: both functions accept an optional `cwd` parameter and thread
the real project root through.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.core.tests_discovery import collect_tests, run_tests


def _build_nested_layout(tmp_path: Path) -> tuple[Path, Path]:
    """Simulate the pragma-style layout: packages/foo/tests/test_*.py.

    Returns (project_root, tests_dir). project_root is the user's cwd;
    tests_dir is the deep path referenced by manifest.project.tests_root.
    """
    project_root = tmp_path
    tests_dir = project_root / "packages" / "foo" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_sample.py").write_text(
        textwrap.dedent(
            """
            def test_sample_green():
                assert True

            def test_sample_red():
                assert False
            """
        ),
        encoding="utf-8",
    )
    return project_root, tests_dir


@trace("REQ-014")
def _assert_collect_tests_on_nested_tests_root(tmp_path: Path) -> None:
    project_root, tests_dir = _build_nested_layout(tmp_path)
    collected = collect_tests(tests_dir, cwd=project_root)
    names = {c.name for c in collected}
    assert {"test_sample_green", "test_sample_red"}.issubset(names), (
        f"collect_tests must find the two tests under nested tests_root; got {names!r}"
    )


@trace("REQ-014")
def _assert_run_tests_on_nested_tests_root(tmp_path: Path) -> None:
    project_root, tests_dir = _build_nested_layout(tmp_path)
    collected = collect_tests(tests_dir, cwd=project_root)
    by_name = {c.name: c for c in collected}
    results = run_tests(
        tests_dir,
        nodeids=[by_name["test_sample_green"].nodeid, by_name["test_sample_red"].nodeid],
        cwd=project_root,
    )
    assert results[by_name["test_sample_green"].nodeid] == "passed", (
        f"run_tests must report the green test as passed under a nested tests_root; got {results!r}"
    )
    assert results[by_name["test_sample_red"].nodeid] == "failed", (
        f"run_tests must report the red test as failed under a nested tests_root; got {results!r}"
    )


def test_req_014_collect_tests_on_nested_tests_root(tmp_path: Path) -> None:
    with set_permutation("collect_tests_on_nested_tests_root"):
        _assert_collect_tests_on_nested_tests_root(tmp_path)


def test_req_014_run_tests_on_nested_tests_root(tmp_path: Path) -> None:
    with set_permutation("run_tests_on_nested_tests_root"):
        _assert_run_tests_on_nested_tests_root(tmp_path)
