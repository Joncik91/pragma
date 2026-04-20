"""Tests for `pragma migrate`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_migrate_writes_v2(monkeypatch: pytest.MonkeyPatch, tmp_project_v1: Path) -> None:
    monkeypatch.chdir(tmp_project_v1)
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["migrated"] is True
    assert payload["from_version"] == "1"
    assert payload["to_version"] == "2"

    raw = yaml.safe_load((tmp_project_v1 / "pragma.yaml").read_text())
    assert raw["version"] == "2"
    assert raw["milestones"][0]["id"] == "M00"


def test_migrate_idempotent_on_v2(monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["migrated"] is False
    assert payload["reason"] == "already_v2"


def test_migrate_rewrites_lockfile(monkeypatch: pytest.MonkeyPatch, tmp_project_v1: Path) -> None:
    monkeypatch.chdir(tmp_project_v1)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    old_lock_text = (tmp_project_v1 / "pragma.lock.json").read_text()

    assert runner.invoke(app, ["migrate"]).exit_code == 0
    new_lock_text = (tmp_project_v1 / "pragma.lock.json").read_text()

    assert new_lock_text != old_lock_text
    assert "M00.S0" in new_lock_text


def test_migrate_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_project_v1: Path) -> None:
    monkeypatch.chdir(tmp_project_v1)
    before = (tmp_project_v1 / "pragma.yaml").read_text()
    result = runner.invoke(app, ["migrate", "--dry-run"])
    assert result.exit_code == 0, result.output
    after = (tmp_project_v1 / "pragma.yaml").read_text()
    assert before == after
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["to_version"] == "2"


def test_migrate_missing_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "manifest_not_found"
