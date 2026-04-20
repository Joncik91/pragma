from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.state import read_state

runner = CliRunner()


def test_cancel_without_active_fails(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["slice", "cancel"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "slice_not_active"


def test_cancel_marks_state(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    result = runner.invoke(app, ["slice", "cancel"])
    assert result.exit_code == 0, result.output

    state = read_state(tmp_project_v2 / ".pragma")
    assert state.active_slice is None
    assert state.slices["M01.S1"].status == "cancelled"


def test_cancel_is_idempotent_hostile(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    assert runner.invoke(app, ["slice", "cancel"]).exit_code == 0
    result = runner.invoke(app, ["slice", "cancel"])
    assert result.exit_code == 1
    assert json.loads(result.output)["error"] == "slice_not_active"
