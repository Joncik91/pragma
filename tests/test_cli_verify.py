"""Tests for `pragma verify manifest`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _init_and_freeze() -> None:
    assert runner.invoke(
        app, ["init", "--brownfield", "--name", "example"]
    ).exit_code == 0
    assert runner.invoke(app, ["freeze"]).exit_code == 0


def test_verify_passes_on_fresh_init_and_freeze(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init_and_freeze()
    result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["check"] == "manifest"


def test_verify_fails_when_manifest_missing(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_not_found"


def test_verify_fails_when_lock_missing(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "lock_not_found"


def test_verify_fails_on_hash_mismatch(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init_and_freeze()
    # Edit pragma.yaml without re-freezing.
    yaml_text = (tmp_project / "pragma.yaml").read_text()
    (tmp_project / "pragma.yaml").write_text(yaml_text.replace("example", "tampered"))

    result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_hash_mismatch"
    assert "pragma freeze" in parsed["remediation"]


def test_verify_fails_on_malformed_yaml(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init_and_freeze()
    (tmp_project / "pragma.yaml").write_text("project: [unclosed")
    result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_syntax_error"
