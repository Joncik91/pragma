from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pragma.core.tests_discovery import (
    collect_tests,
    expected_test_name,
    run_tests,
)


def test_expected_test_name() -> None:
    assert expected_test_name("REQ-001", "valid_credentials") == "test_req_001_valid_credentials"
    assert expected_test_name("REQ-0017", "a") == "test_req_0017_a"


def _write_tests_tree(tmp_path: Path, *tests: tuple[str, str]) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for fname, body in tests:
        (tests_dir / fname).write_text(textwrap.dedent(body), encoding="utf-8")
    return tests_dir


def test_collect_tests_finds_matching_test_names(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(
        tmp_path,
        (
            "test_req_001.py",
            """
            def test_req_001_valid_credentials():
                assert False

            def test_req_001_weak_password():
                assert False

            def test_unrelated():
                assert True
            """,
        ),
    )
    found = collect_tests(tests_dir)
    assert "test_req_001_valid_credentials" in {n.name for n in found}
    assert "test_req_001_weak_password" in {n.name for n in found}
    assert "test_unrelated" in {n.name for n in found}


def test_run_tests_returns_pass_fail_map(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(
        tmp_path,
        (
            "test_req_001.py",
            """
            def test_req_001_red():
                assert False

            def test_req_001_green():
                assert True
            """,
        ),
    )
    collected = collect_tests(tests_dir)
    by_name = {n.name: n for n in collected}
    results = run_tests(
        tests_dir,
        nodeids=[by_name["test_req_001_red"].nodeid, by_name["test_req_001_green"].nodeid],
    )
    assert results[by_name["test_req_001_red"].nodeid] == "failed"
    assert results[by_name["test_req_001_green"].nodeid] == "passed"


def test_collect_on_empty_dir(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    assert collect_tests(tests_dir) == []


def test_collect_tests_ignores_parent_addopts_q(tmp_path: Path) -> None:
    """Collector must find tests even when the parent pyproject pins -q in addopts.

    pytest 9's `-q --collect-only` prints compact file summaries
    (`path.py: 4`) instead of per-test nodeids, which makes the nodeid
    parser return zero hits. The collector must override addopts or
    ask pytest for nodeid-per-line output so it works regardless of
    the user's pyproject.
    """
    tests_dir = _write_tests_tree(
        tmp_path,
        (
            "test_req_001.py",
            """
            def test_req_001_a():
                assert True

            def test_req_001_b():
                assert True
            """,
        ),
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q"\n',
        encoding="utf-8",
    )
    found = collect_tests(tests_dir)
    names = {n.name for n in found}
    assert "test_req_001_a" in names
    assert "test_req_001_b" in names


def test_collect_raises_on_collect_errors(tmp_path: Path) -> None:
    tests_dir = _write_tests_tree(
        tmp_path,
        ("test_broken.py", "import nonexistent_module\n"),
    )
    from pragma.core.tests_discovery import CollectError

    with pytest.raises(CollectError, match=r"nonexistent_module"):
        collect_tests(tests_dir)
