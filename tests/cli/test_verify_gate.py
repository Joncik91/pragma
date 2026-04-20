from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_verify_gate_no_active_slice(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["active_slice"] is None


def test_verify_gate_locked_missing_tests(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "unlock_missing_tests"


def test_verify_gate_locked_with_red_tests_passes(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 0, result.output


def test_verify_gate_manifest_hash_drift(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    yaml_path = tmp_project_v2 / "pragma.yaml"
    yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    yaml_data["project"]["name"] = "drifted"
    yaml_path.write_text(
        yaml.safe_dump(yaml_data, sort_keys=False), encoding="utf-8"
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "gate_hash_drift"
