"""Dogfood tests for REQ-001 — the CLI stable-JSON contract.

Thin convention-named wrappers around code paths that existing
descriptive-named tests already cover. These exist so `pragma report`
joins the @trace'd CLI entry points to the declared permutations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pragma_sdk import set_permutation
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_req_001_init_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with set_permutation("init_success"):
        result = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "pragma.yaml" in payload["created"]


def test_req_001_init_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pragma.yaml").write_text("existing: true\n", encoding="utf-8")
    with set_permutation("init_duplicate"):
        result = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"] == "already_initialised"


def _init_and_chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert result.exit_code == 0


def test_req_001_freeze_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_and_chdir(tmp_path, monkeypatch)
    with set_permutation("freeze_success"):
        result = runner.invoke(app, ["freeze"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "manifest_hash" in payload


def test_req_001_freeze_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with set_permutation("freeze_missing"):
        result = runner.invoke(app, ["freeze"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"] == "manifest_not_found"


def test_req_001_verify_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_and_chdir(tmp_path, monkeypatch)
    freeze = runner.invoke(app, ["freeze"])
    assert freeze.exit_code == 0
    with set_permutation("verify_success"):
        result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True


def test_req_001_verify_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_and_chdir(tmp_path, monkeypatch)
    runner.invoke(app, ["freeze"])
    yaml_path = tmp_path / "pragma.yaml"
    # Change the parsed content (not just a comment) so hash_manifest differs.
    yaml_path.write_text(
        yaml_path.read_text().replace('name: "demo"', 'name: "drifted"'),
        encoding="utf-8",
    )
    with set_permutation("verify_mismatch"):
        result = runner.invoke(app, ["verify", "manifest"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"] == "manifest_hash_mismatch"


def test_req_001_doctor_always_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with set_permutation("doctor_always_zero"):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
