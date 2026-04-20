from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.integrity import read_stored_hash

runner = CliRunner()


def test_init_writes_claude_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert r.exit_code == 0, r.output

    settings = tmp_path / ".claude" / "settings.json"
    assert settings.exists()
    payload = json.loads(settings.read_text())
    assert "SessionStart" in payload["hooks"]
    assert "PreToolUse" in payload["hooks"]


def test_init_writes_hash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "d"]).exit_code == 0
    h = read_stored_hash(tmp_path / ".pragma")
    assert h is not None
    assert h.startswith("sha256:")


def test_init_force_overwrites_existing_settings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text('{"old":true}', encoding="utf-8")
    r = runner.invoke(app, ["init", "--brownfield", "--name", "d", "--force"])
    assert r.exit_code == 0, r.output
    payload = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" in payload


def test_init_pre_commit_config_has_battery(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "d"]).exit_code == 0
    cfg = (tmp_path / ".pre-commit-config.yaml").read_text()
    assert "gitleaks" in cfg
    assert "ruff" in cfg
    assert "mypy" in cfg
    assert "semgrep" in cfg
    assert "pragma verify all" in cfg
