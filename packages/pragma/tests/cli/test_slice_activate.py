from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.audit import read_audit
from pragma.core.state import read_state

runner = CliRunner()


def test_activate_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0

    result = runner.invoke(app, ["slice", "activate", "M01.S1"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["slice"] == "M01.S1"
    assert payload["gate"] == "LOCKED"

    state = read_state(tmp_project_v2 / ".pragma")
    assert state.active_slice == "M01.S1"
    assert state.gate == "LOCKED"

    audit = read_audit(tmp_project_v2 / ".pragma")
    assert audit[-1]["event"] == "slice_activated"


def test_activate_unknown_slice(monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0

    result = runner.invoke(app, ["slice", "activate", "M99.S99"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "slice_not_found"


def test_activate_when_another_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0

    result = runner.invoke(app, ["slice", "activate", "M01.S1"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "slice_already_active"


def test_activate_with_force(monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0

    result = runner.invoke(app, ["slice", "activate", "M01.S1", "--force"])
    assert result.exit_code == 0, result.output
