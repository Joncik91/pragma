from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_status_with_no_state(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["slice", "status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["active_slice"] is None
    assert payload["gate"] is None
    assert payload["slices"] == {}


def test_status_reflects_active(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    result = runner.invoke(app, ["slice", "status"])
    payload = json.loads(result.output)
    assert payload["active_slice"] == "M01.S1"
    assert payload["gate"] == "LOCKED"
    assert payload["slices"]["M01.S1"] == {"status": "in_progress", "gate": "LOCKED"}
