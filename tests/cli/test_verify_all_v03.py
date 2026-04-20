from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_verify_all_runs_all_six_checks(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    r = runner.invoke(app, ["verify", "all"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert set(payload["checks"]) >= {"manifest", "gate", "integrity"}
