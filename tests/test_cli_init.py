"""Tests for `pragma init --brownfield`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.manifest import load_manifest

runner = CliRunner()


def test_init_creates_manifest_precommit_and_readme(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example-project"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_project / "pragma.yaml").exists()
    assert (tmp_project / ".pre-commit-config.yaml").exists()
    assert (tmp_project / "PRAGMA.md").exists()


def test_init_scaffolded_manifest_is_schema_valid(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example"])
    assert result.exit_code == 0

    manifest = load_manifest(tmp_project / "pragma.yaml")
    assert manifest.project.name == "example"
    assert manifest.project.mode == "brownfield"
    assert manifest.project.language == "python"
    assert manifest.requirements == ()


def test_init_with_special_chars_in_name_produces_valid_yaml(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Project names with YAML-special characters must still produce a valid manifest."""
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(
        app, ["init", "--brownfield", "--name", "team:alpha#1"]
    )
    assert result.exit_code == 0, result.stdout

    manifest = load_manifest(tmp_project / "pragma.yaml")
    assert manifest.project.name == "team:alpha#1"


def test_init_refuses_to_overwrite_existing_manifest(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    (tmp_project / "pragma.yaml").write_text("existing: file\n")
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example"])
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "already_initialised"


def test_init_force_overwrites_existing(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    (tmp_project / "pragma.yaml").write_text("existing: file\n")
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example", "--force"])
    assert result.exit_code == 0
    assert 'name: "example"' in (tmp_project / "pragma.yaml").read_text()


def test_init_name_defaults_to_directory_name(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["init", "--brownfield"])
    assert result.exit_code == 0
    yaml_text = (tmp_project / "pragma.yaml").read_text()
    assert f'name: "{tmp_project.name}"' in yaml_text


def test_init_prints_success_json(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert "created" in parsed
    assert set(parsed["created"]) == {
        "pragma.yaml",
        ".pre-commit-config.yaml",
        "PRAGMA.md",
    }
