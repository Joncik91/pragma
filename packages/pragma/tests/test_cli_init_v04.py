"""Tests for v0.4 init additions: .pragma/spans/ dir + .gitignore entries."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_init_creates_spans_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / ".pragma" / "spans").is_dir()


def test_init_appends_gitignore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test"])
    assert result.exit_code == 0, result.stdout
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".pragma/spans/" in gitignore
    assert ".pragma/pytest-junit.xml" in gitignore


def test_init_gitignore_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".gitignore").write_text(".pragma/spans/\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test", "--force"])
    assert result.exit_code == 0, result.stdout
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.count(".pragma/spans/") == 1


def test_init_writes_pytest_ini_when_no_pytest_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test"])
    assert result.exit_code == 0, result.stdout
    ini = tmp_path / "pytest.ini"
    assert ini.exists()
    assert "--junit-xml=.pragma/pytest-junit.xml" in ini.read_text(encoding="utf-8")


def test_init_respects_existing_pyproject_pytest_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test"])
    assert result.exit_code == 0, result.stdout
    assert not (tmp_path / "pytest.ini").exists()


def test_init_respects_existing_pytest_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -v\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "test"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "pytest.ini").read_text(encoding="utf-8") == "[pytest]\naddopts = -v\n"
