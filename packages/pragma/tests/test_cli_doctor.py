"""Tests for the `pragma doctor` stub.

v0.1 ships a stub whose only job is to print diagnostic info about the
local Pragma install + project state. The self-heal features (emergency
unlock, hook integrity restoration) land in v0.2 and v0.3.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_doctor_prints_version_and_cwd(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["pragma_version"] == "1.0.0"
    assert Path(parsed["cwd"]) == tmp_project.resolve()
    assert parsed["manifest_exists"] is False
    assert parsed["lock_exists"] is False


def test_doctor_reports_files_after_init(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    result = runner.invoke(app, ["doctor"])
    parsed = json.loads(result.stdout)
    assert parsed["manifest_exists"] is True
    assert parsed["lock_exists"] is False
    assert parsed["pre_commit_config_exists"] is True


def test_doctor_reports_lock_after_freeze(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["doctor"])
    parsed = json.loads(result.stdout)
    assert parsed["lock_exists"] is True


def test_doctor_always_exits_zero(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor is a diagnostic tool; it never fails the shell.

    Concerns like 'lock is missing' are reported in the payload, not as
    a non-zero exit — the user runs doctor to find out *what* is wrong,
    so the tool must itself succeed.
    """
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
