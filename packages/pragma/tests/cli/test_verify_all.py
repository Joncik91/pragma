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
    # v1.0.2: verify all runs the full check set now that KI-11 has
    # cleared Pragma's own discipline debt. The Stop hook invokes
    # verify all to decide whether a turn can end; any check missing
    # here becomes a silent gate hole.
    assert payload["checks"] == ["manifest", "gate", "integrity", "discipline", "commits"]


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
