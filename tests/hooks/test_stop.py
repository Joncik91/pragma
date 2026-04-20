from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.hooks.stop import handle


runner = CliRunner()


def test_stop_allows_on_clean_state(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    out = handle({"session_id": "x"}, tmp_project_v2)
    assert out.get("decision") != "block"


def test_stop_blocks_on_manifest_drift(
    monkeypatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    data = yaml.safe_load((tmp_project_v2 / "pragma.yaml").read_text(encoding="utf-8"))
    data["project"]["name"] = "drifted"
    (tmp_project_v2 / "pragma.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    out = handle({"session_id": "x"}, tmp_project_v2)
    assert out["decision"] == "block"
    assert "manifest" in out["reason"].lower()


def test_stop_blocks_on_locked_with_missing_tests(
    monkeypatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = handle({"session_id": "x"}, tmp_project_v2)
    assert out["decision"] == "block"
