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
    """KI-7: default battery contains what works OOTB; mypy/semgrep/deptry are opt-in."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "d"]).exit_code == 0
    cfg = (tmp_path / ".pre-commit-config.yaml").read_text()
    # Active, out-of-the-box hooks.
    assert "gitleaks" in cfg
    assert "ruff" in cfg
    assert "pip-audit" in cfg
    assert "pragma verify all" in cfg
    # mypy / semgrep / deptry are documented-but-commented-out opt-ins.
    assert "# - repo: https://github.com/pre-commit/mirrors-mypy" in cfg
    assert "# - repo: https://github.com/returntocorp/semgrep" in cfg
    assert "# - repo: https://github.com/fpgmaas/deptry" in cfg
