"""Red tests for REQ-028 — spec add-requirement assigns milestone+slice.

BUG-031. `pragma spec add-requirement` had no flags for milestone or
slice. On v2 manifests every requirement needs both — REQ-008
enforces this at freeze time. Users had to hand-edit pragma.yaml
after every add-requirement call. Fix adds --milestone / --slice
flags to the CLI.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _bootstrap_v2_manifest(tmp_project: Path) -> None:
    """Greenfield init writes a v2 manifest + scaffold."""
    import os

    cwd = Path.cwd()
    try:
        os.chdir(tmp_project)
        assert (
            runner.invoke(
                app,
                ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
            ).exit_code
            == 0
        )
        # Replace the REQ-000 placeholder with a real slice we can target.
        (tmp_project / "pragma.yaml").write_text(
            textwrap.dedent(
                """
                version: '2'
                project:
                  name: demo
                  mode: greenfield
                  language: python
                  source_root: src/
                  tests_root: tests/
                milestones:
                - id: M01
                  title: m
                  description: m
                  depends_on: []
                  slices:
                  - id: M01.S1
                    title: first
                    description: first
                    requirements: []
                requirements: []
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
    finally:
        os.chdir(cwd)


@trace("REQ-028")
def _assert_accepts_milestone_and_slice(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap_v2_manifest(tmp_project)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "t",
            "--description",
            "d",
            "--touches",
            "src/x.py",
            "--permutation",
            "happy|h|success",
            "--milestone",
            "M01",
            "--slice",
            "M01.S1",
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = yaml.safe_load((tmp_project / "pragma.yaml").read_text(encoding="utf-8"))
    req = next(r for r in data["requirements"] if r["id"] == "REQ-001")
    assert req["milestone"] == "M01"
    assert req["slice"] == "M01.S1"


@trace("REQ-028")
def _assert_freeze_passes_after_add(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap_v2_manifest(tmp_project)
    monkeypatch.chdir(tmp_project)
    assert (
        runner.invoke(
            app,
            [
                "spec",
                "add-requirement",
                "--id",
                "REQ-001",
                "--title",
                "t",
                "--description",
                "d",
                "--touches",
                "src/x.py",
                "--permutation",
                "happy|h|success",
                "--milestone",
                "M01",
                "--slice",
                "M01.S1",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["verify", "manifest"]).exit_code == 0


@trace("REQ-028")
def _assert_rejects_unknown_slice(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap_v2_manifest(tmp_project)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "t",
            "--description",
            "d",
            "--touches",
            "src/x.py",
            "--permutation",
            "happy|h|success",
            "--milestone",
            "M99",
            "--slice",
            "M99.S99",
        ],
    )
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["error"] == "slice_not_found"
    # Remediation should list the declared slice ids.
    assert "M01.S1" in payload["remediation"] or "declared" in payload["remediation"].lower()


def test_req_028_accepts_milestone_and_slice(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("accepts_milestone_and_slice"):
        _assert_accepts_milestone_and_slice(tmp_project, monkeypatch)


def test_req_028_freeze_passes_after_add(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("freeze_passes_after_add"):
        _assert_freeze_passes_after_add(tmp_project, monkeypatch)


def test_req_028_rejects_unknown_slice(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("rejects_unknown_slice"):
        _assert_rejects_unknown_slice(tmp_project, monkeypatch)
