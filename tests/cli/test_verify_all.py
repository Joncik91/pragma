from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_verify_all_fresh_project(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["verify", "all"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["checks"] == ["manifest", "gate", "discipline", "integrity"]


def test_verify_all_fails_fast_on_manifest(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    yaml_path = tmp_project_v2 / "pragma.yaml"
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8").replace("demo", "tampered"),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["verify", "all"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "manifest_hash_mismatch"
