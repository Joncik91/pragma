"""Red tests for REQ-020 - slice complete emits junit for the whole project.

BUG-021. `pragma slice complete` invokes pytest on only the current
slice's nodeids. The resulting junit.xml overwrites the previous
slice's, so `pragma report` across multiple shipped slices sees only
the last one's tests verified and flags every earlier permutation as
`missing`. Fix: after the per-slice gate check passes, regenerate
junit from a full-suite pytest run.
"""

from __future__ import annotations

import json
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.tests_discovery import run_full_suite_junit

runner = CliRunner()


def _write_two_tests(tmp_path: Path) -> Path:
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
    (tests_dir / "test_req_002.py").write_text(
        textwrap.dedent(
            """
            def test_req_002_a():
                assert True
            """
        ),
        encoding="utf-8",
    )
    return tests_dir


@trace("REQ-020")
def _assert_run_full_suite_writes_junit_for_all_tests(tmp_path: Path) -> None:
    tests_dir = _write_two_tests(tmp_path)
    junit_path = tmp_path / ".pragma" / "pytest-junit.xml"
    ok = run_full_suite_junit(tests_dir=tests_dir, cwd=tmp_path, junit_xml=junit_path)
    assert ok, "run_full_suite_junit must succeed when tests pass"
    assert junit_path.exists()
    tree = ET.parse(junit_path)
    names = {tc.get("name") for tc in tree.iter("testcase")}
    assert {"test_req_001_a", "test_req_001_b", "test_req_002_a"}.issubset(names), (
        f"junit.xml must include every test in tests_dir; got {names!r}"
    )


def _build_two_slice_project(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scaffold greenfield + declare two one-permutation slices."""
    monkeypatch.chdir(tmp_project)
    assert (
        runner.invoke(
            app,
            ["init", "--greenfield", "--name", "twoslice", "--language", "python", "--force"],
        ).exit_code
        == 0
    )
    (tmp_project / "pragma.yaml").write_text(
        textwrap.dedent(
            """
            version: '2'
            project:
              name: twoslice
              mode: greenfield
              language: python
              source_root: src/
              tests_root: tests/
            milestones:
            - id: M01
              title: two slices
              description: two slices
              depends_on: []
              slices:
              - id: M01.S1
                title: first
                description: first
                requirements: [REQ-001]
              - id: M01.S2
                title: second
                description: second
                requirements: [REQ-002]
            requirements:
            - id: REQ-001
              title: first
              description: first
              touches: [src/first.py]
              permutations:
              - id: a
                description: a
                expected: success
              milestone: M01
              slice: M01.S1
            - id: REQ-002
              title: second
              description: second
              touches: [src/second.py]
              permutations:
              - id: a
                description: a
                expected: success
              milestone: M01
              slice: M01.S2
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0


def _ship(
    tmp_project: Path,
    slice_id: str,
    src_name: str,
    test_name: str,
    logic_id: str,
    perm: str,
) -> None:
    """Run one full slice activate -> unlock -> complete cycle."""
    (tmp_project / "src" / src_name).write_text(
        textwrap.dedent(
            f"""
            from pragma_sdk import trace

            @trace("{logic_id}")
            def f():
                raise NotImplementedError
            """
        ),
        encoding="utf-8",
    )
    (tmp_project / "tests" / test_name).write_text(
        textwrap.dedent(
            f"""
            from pragma_sdk import set_permutation
            from {src_name[:-3]} import f

            def test_{logic_id.lower().replace("-", "_")}_{perm}():
                with set_permutation("{perm}"):
                    assert f() == "ok"
            """
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["slice", "activate", slice_id]).exit_code == 0
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    (tmp_project / "src" / src_name).write_text(
        textwrap.dedent(
            f"""
            from pragma_sdk import trace

            @trace("{logic_id}")
            def f():
                return "ok"
            """
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["slice", "complete"]).exit_code == 0


@trace("REQ-020")
def _assert_slice_complete_regenerates_full_junit(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_two_slice_project(tmp_project, monkeypatch)
    _ship(tmp_project, "M01.S1", "first.py", "test_req_001.py", "REQ-001", "a")
    _ship(tmp_project, "M01.S2", "second.py", "test_req_002.py", "REQ-002", "a")

    # After both slices ship, the PIL must see both as verified.
    result = runner.invoke(app, ["report", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert summary["ok"] == 2, (
        f"PIL must show 2 verified after shipping both slices; got {summary!r}"
    )
    assert summary["missing"] == 0, (
        f"PIL must show 0 missing after shipping both slices; got {summary!r}"
    )


def test_req_020_run_full_suite_writes_junit_for_all_tests(tmp_path: Path) -> None:
    with set_permutation("run_full_suite_writes_junit_for_all_tests"):
        _assert_run_full_suite_writes_junit_for_all_tests(tmp_path)


def test_req_020_slice_complete_regenerates_full_junit(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("slice_complete_regenerates_full_junit"):
        _assert_slice_complete_regenerates_full_junit(tmp_project, monkeypatch)


def test_req_020_smoke_ships_two_slices_and_pil_sees_both() -> None:
    with set_permutation("smoke_ships_two_slices_and_pil_sees_both"):
        text = (Path(__file__).resolve().parents[4] / "scripts" / "pre-release-smoke.sh").read_text(
            encoding="utf-8"
        )
        # Smoke script must ship at least two slices in the end-to-end
        # PIL section (so it would have caught BUG-021).
        assert text.count("slice activate") >= 2, (
            "pre-release-smoke.sh must ship at least two slices to catch BUG-021"
        )
        # And assert the final PIL shows ok>=2 (not 1).
        assert '"ok"]' in text or "summary.ok" in text or "ok_count" in text, (
            "smoke script must parse summary.ok and assert it reflects all shipped slices"
        )
