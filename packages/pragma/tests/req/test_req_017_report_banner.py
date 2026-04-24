"""Red tests for REQ-017 - report surfaces missing artifacts.

BUG-020 companion. When the PIL aggregator computes "missing" for
>=50% of permutations because junit.xml or spans/ is absent,
`pragma report --human` and `--json` must include a diagnostic
banner naming the absent artifact and the one-line fix, instead of a
silent wall of "missing" rows with "No remediation."
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _minimal_v2_manifest(tmp_project: Path) -> None:
    """Scaffold a minimal v2 manifest with one REQ + permutation."""
    (tmp_project / "pragma.yaml").write_text(
        (
            "version: '2'\n"
            "project:\n"
            "  name: demo\n"
            "  mode: brownfield\n"
            "  language: python\n"
            "  source_root: src/\n"
            "  tests_root: tests/\n"
            "milestones:\n"
            "- id: M01\n"
            "  title: demo\n"
            "  description: demo\n"
            "  depends_on: []\n"
            "  slices:\n"
            "  - id: M01.S1\n"
            "    title: demo\n"
            "    description: demo\n"
            "    requirements: [REQ-001]\n"
            "requirements:\n"
            "- id: REQ-001\n"
            "  title: demo\n"
            "  description: demo\n"
            "  touches: [src/demo.py]\n"
            "  permutations:\n"
            "  - id: happy\n"
            "    description: happy\n"
            "    expected: success\n"
            "  milestone: M01\n"
            "  slice: M01.S1\n"
        ),
        encoding="utf-8",
    )


@trace("REQ-017")
def _assert_banner_when_junit_absent(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _minimal_v2_manifest(tmp_project)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    # No .pragma/pytest-junit.xml created.
    result = runner.invoke(app, ["report", "--human"])
    assert result.exit_code == 0
    # The diagnostic banner should name the missing artifact.
    assert "pytest-junit.xml" in result.stdout, (
        f"Markdown report must surface the missing junit.xml artifact; got:\n{result.stdout}"
    )


@trace("REQ-017")
def _assert_banner_when_spans_absent(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _minimal_v2_manifest(tmp_project)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    # Create a non-empty junit.xml that reports one test name matching
    # the declared permutation so it wouldn't register as missing-due-to-junit.
    junit_path = tmp_project / ".pragma" / "pytest-junit.xml"
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<testsuites>\n"
        "  <testsuite name='pytest' tests='1' failures='0' errors='0' skipped='0'>\n"
        "    <testcase classname='tests.test_req_001' name='test_req_001_happy'/>\n"
        "  </testsuite>\n"
        "</testsuites>\n",
        encoding="utf-8",
    )
    # No spans dir — should trigger the "mocked" path for the permutation
    # (junit has the test, but no span witnessed it), not "missing".
    # The banner should still mention the empty/missing spans dir.
    result = runner.invoke(app, ["report", "--human"])
    assert result.exit_code == 0
    assert "spans" in result.stdout.lower(), (
        f"Markdown report must surface the empty/missing spans directory; got:\n{result.stdout}"
    )


@trace("REQ-017")
def _assert_no_banner_on_happy_path(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _minimal_v2_manifest(tmp_project)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    junit_path = tmp_project / ".pragma" / "pytest-junit.xml"
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<testsuites>\n"
        "  <testsuite name='pytest' tests='1' failures='0' errors='0' skipped='0'>\n"
        "    <testcase classname='tests.test_req_001' name='test_req_001_happy'/>\n"
        "  </testsuite>\n"
        "</testsuites>\n",
        encoding="utf-8",
    )
    spans_dir = tmp_project / ".pragma" / "spans"
    spans_dir.mkdir(parents=True, exist_ok=True)
    (spans_dir / "run.jsonl").write_text(
        json.dumps(
            {
                "attrs": {"pragma.logic_id": "REQ-001", "pragma.permutation": "happy"},
                "span_name": "REQ-001:demo",
                "status": "ok",
                "test_nodeid": "tests/test_req_001.py::test_req_001_happy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["report", "--human"])
    assert result.exit_code == 0
    # Happy path: banner should NOT appear.
    assert "pytest-junit.xml not found" not in result.stdout, (
        f"No banner on happy path; got:\n{result.stdout}"
    )
    assert "spans directory is empty" not in result.stdout


def test_req_017_report_banner_when_junit_absent(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("report_banner_when_junit_absent"):
        _assert_banner_when_junit_absent(tmp_project, monkeypatch)


def test_req_017_report_banner_when_spans_absent(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("report_banner_when_spans_absent"):
        _assert_banner_when_spans_absent(tmp_project, monkeypatch)


def test_req_017_report_no_banner_on_happy_path(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("report_no_banner_on_happy_path"):
        _assert_no_banner_on_happy_path(tmp_project, monkeypatch)
