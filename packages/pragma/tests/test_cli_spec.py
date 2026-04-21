"""Tests for `pragma spec add-requirement`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _init(tmp_project: Path) -> None:
    result = runner.invoke(app, ["init", "--brownfield", "--name", "example"])
    assert result.exit_code == 0


def test_add_requirement_writes_requirement_to_yaml(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "User can log in",
            "--description",
            "Operator signs in with email + password.",
            "--touches",
            "src/auth/login.py",
            "--permutation",
            "valid_credentials|Valid email and strong password returns JWT|success",
            "--permutation",
            "wrong_password|Wrong password returns 401|reject",
        ],
    )
    assert result.exit_code == 0, result.stdout

    loaded = yaml.safe_load((tmp_project / "pragma.yaml").read_text())
    reqs = loaded["requirements"]
    assert len(reqs) == 1
    r = reqs[0]
    assert r["id"] == "REQ-001"
    assert r["title"] == "User can log in"
    assert r["touches"] == ["src/auth/login.py"]
    assert len(r["permutations"]) == 2
    assert r["permutations"][0]["id"] == "valid_credentials"
    assert r["permutations"][1]["expected"] == "reject"


def test_add_requirement_rejects_duplicate_id(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    base_args = [
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
    ]
    result1 = runner.invoke(app, base_args)
    assert result1.exit_code == 0, result1.stdout

    result2 = runner.invoke(app, base_args)
    assert result2.exit_code != 0
    parsed = json.loads(result2.stdout)
    assert parsed["error"] == "duplicate_requirement_id"


def test_add_requirement_rejects_malformed_permutation_arg(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
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
            "missing_pipes_format",
        ],
    )
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "invalid_permutation_spec"


def test_add_requirement_rejects_bad_requirement_id(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "notreq",
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
    assert result.exit_code != 0
    parsed = json.loads(result.stdout)
    assert parsed["error"] == "manifest_schema_error"


def test_add_requirement_accepts_multiple_touches(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
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
            "src/a.py",
            "--touches",
            "src/b.py",
            "--permutation",
            "p|d|success",
        ],
    )
    assert result.exit_code == 0
    loaded = yaml.safe_load((tmp_project / "pragma.yaml").read_text())
    assert loaded["requirements"][0]["touches"] == ["src/a.py", "src/b.py"]


def test_add_requirement_accepts_pipe_in_description(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Descriptions can contain '|' — only first 2 pipes are significant."""
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
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
            "p|Accepts (foo | bar) | doc|success",
        ],
    )
    assert result.exit_code == 0, result.stdout
    loaded = yaml.safe_load((tmp_project / "pragma.yaml").read_text())
    perm = loaded["requirements"][0]["permutations"][0]
    assert perm["description"] == "Accepts (foo | bar) | doc"
    assert perm["expected"] == "success"


def test_add_requirement_emits_added_json(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    _init(tmp_project)
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-042",
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
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["added"]["id"] == "REQ-042"
    assert parsed["added"]["permutation_count"] == 1
