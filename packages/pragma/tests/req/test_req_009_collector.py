"""Dogfood tests for REQ-009 - collect_tests finds nodeids regardless of parent addopts.

pytest 9's `-q --collect-only` compacts output to file summaries
(`path.py: 4`) instead of per-test nodeids. Before v1.0.1 the pragma
collector inherited `-q` from the parent pyproject's addopts so it
returned zero collected tests, which made every slice unlock report
all required tests as missing.

Wrapped in @trace("REQ-009") helpers so the spans carry
logic_id=REQ-009 and the PIL aggregator does not tag these as mocked.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.core.tests_discovery import collect_tests


def _write_tests_tree(tmp_path: Path) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent(
            """
            def test_req_001_a():
                assert True

            def test_req_001_b():
                assert True
            """
        ),
        encoding="utf-8",
    )
    return tests_dir


@trace("REQ-009")
def _assert_collects_under_parent_addopts_q(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q"\n',
        encoding="utf-8",
    )
    names = {c.name for c in collect_tests(tests_dir)}
    assert {"test_req_001_a", "test_req_001_b"}.issubset(names), (
        f"collect_tests must ignore parent -q addopts; got {names!r}"
    )


@trace("REQ-009")
def _assert_collects_from_clean_dir(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(tmp_path)
    names = {c.name for c in collect_tests(tests_dir)}
    assert {"test_req_001_a", "test_req_001_b"}.issubset(names)


def test_req_009_collects_under_parent_addopts_q(tmp_path: Path) -> None:
    with set_permutation("collects_under_parent_addopts_q"):
        _assert_collects_under_parent_addopts_q(tmp_path)


def test_req_009_collects_from_clean_dir(tmp_path: Path) -> None:
    with set_permutation("collects_from_clean_dir"):
        _assert_collects_from_clean_dir(tmp_path)
