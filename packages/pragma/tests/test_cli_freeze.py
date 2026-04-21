"""Tests for `pragma freeze`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _init() -> None:
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0


def test_freeze_creates_lockfile(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _init()
    result = runner.invoke(app, ["freeze"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_project / "pragma.lock.json").exists()

    lock = json.loads((tmp_project / "pragma.lock.json").read_text())
    assert lock["version"] == "1"
    assert lock["manifest_hash"].startswith("sha256:")


def test_freeze_is_idempotent(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _init()
    runner.invoke(app, ["freeze"])
    h1 = json.loads((tmp_project / "pragma.lock.json").read_text())["manifest_hash"]

    runner.invoke(app, ["freeze"])
    h2 = json.loads((tmp_project / "pragma.lock.json").read_text())["manifest_hash"]
    assert h1 == h2


def test_freeze_updates_hash_when_yaml_changes(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init()
    runner.invoke(app, ["freeze"])
    h1 = json.loads((tmp_project / "pragma.lock.json").read_text())["manifest_hash"]

    runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "t",
            "--description",
            "d",
            "--touches",
            "src/x.py",
            "--permutation",
            "p|d|success",
        ],
    )
    runner.invoke(app, ["freeze"])
    h2 = json.loads((tmp_project / "pragma.lock.json").read_text())["manifest_hash"]
    assert h1 != h2


def test_freeze_errors_when_no_manifest(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["freeze"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_not_found"


def test_freeze_errors_on_malformed_yaml(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    (tmp_project / "pragma.yaml").write_text("project: [unclosed")
    result = runner.invoke(app, ["freeze"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_syntax_error"


def test_freeze_emits_json_error_for_unknown_milestone_ref(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """freeze must not crash with TypeError when a requirement references an unknown milestone.

    The v1 model_validator raises ValueError for 'unknown milestone M99',
    which pydantic wraps as ValidationError with ctx.error = the original
    ValueError object. json.dumps can't serialize that exception, so the
    CLI's error-rendering path crashed with TypeError before v1.0.1.
    """
    monkeypatch.chdir(tmp_project)
    (tmp_project / "pragma.yaml").write_text(
        "version: '2'\n"
        "project:\n"
        "  name: testp\n"
        "  mode: brownfield\n"
        "  language: python\n"
        "  source_root: src/\n"
        "  tests_root: tests/\n"
        "requirements:\n"
        "- id: REQ-001\n"
        "  title: foo\n"
        "  description: bar\n"
        "  touches:\n"
        "  - src/x.py\n"
        "  permutations:\n"
        "  - id: p\n"
        "    description: d\n"
        "    expected: success\n"
        "  milestone: M99\n"
        "  slice: M99.S1\n"
        "milestones:\n"
        "- id: M01\n"
        "  title: m1\n"
        "  description: d\n"
        "  depends_on: []\n"
        "  slices:\n"
        "  - id: M01.S1\n"
        "    title: s1\n"
        "    description: d\n"
        "    requirements:\n"
        "    - REQ-001\n"
    )
    result = runner.invoke(app, ["freeze"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_schema_error"
    assert "milestone" in parsed["message"].lower()


def test_freeze_emits_ok_json_with_hash(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    _init()
    result = runner.invoke(app, ["freeze"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["manifest_hash"].startswith("sha256:")
    assert "pragma.lock.json" in parsed["wrote"]
