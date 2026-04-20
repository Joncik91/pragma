from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.integrity import compute_settings_hash, write_stored_hash

runner = CliRunner()


def test_verify_integrity_no_settings_ok(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "integrity"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["reason"] == "no_settings"


def test_verify_integrity_matches(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks": {}}\n', encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    write_stored_hash(pragma_dir, compute_settings_hash(settings))
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "integrity"])
    assert r.exit_code == 0, r.output


def test_verify_integrity_mismatch(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks": {}}\n', encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    write_stored_hash(pragma_dir, "sha256:" + "0" * 64)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "integrity"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "integrity_mismatch"


def test_verify_integrity_not_sealed(monkeypatch, tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "integrity"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "hash_not_found"
