from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.integrity import read_stored_hash


runner = CliRunner()


def test_hooks_seal_writes_hash(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks":{}}', encoding="utf-8")
    (tmp_path / ".pragma").mkdir()
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hooks", "seal"])
    assert r.exit_code == 0, r.output
    assert read_stored_hash(tmp_path / ".pragma") is not None


def test_hooks_seal_without_settings_errors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hooks", "seal"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "settings_not_found"


def test_hooks_verify(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hooks", "verify"])
    assert r.exit_code == 0


def test_hooks_show(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks":{"SessionStart":[]}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hooks", "show"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["ok"] is True
    assert payload["settings"]["hooks"]["SessionStart"] == []
