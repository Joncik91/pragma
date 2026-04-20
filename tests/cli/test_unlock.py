from __future__ import annotations

import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _activate(tmp_project_v2: Path) -> None:
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0


def test_unlock_without_active_fails(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    result = runner.invoke(app, ["unlock"])
    assert result.exit_code == 1
    assert json.loads(result.output)["error"] == "slice_not_active"


def test_unlock_with_missing_tests(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _activate(tmp_project_v2)
    (tmp_project_v2 / "tests").mkdir(exist_ok=True)
    result = runner.invoke(app, ["unlock"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "unlock_missing_tests"
    assert "test_req_001_happy" in payload["context"]["missing"]
    assert "test_req_001_sad" in payload["context"]["missing"]


def test_unlock_with_passing_tests_rejects(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _activate(tmp_project_v2)
    (tmp_project_v2 / "tests").mkdir(exist_ok=True)
    (tmp_project_v2 / "tests" / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert True
            def test_req_001_sad(): assert True
        """),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["unlock"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "unlock_test_passing"
    assert len(payload["context"]["passing"]) == 2


def test_unlock_with_failing_tests_succeeds(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _activate(tmp_project_v2)
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert False
            def test_req_001_sad(): assert False
        """),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["unlock"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["gate"] == "UNLOCKED"


def test_unlock_from_unlocked_rejects(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _activate(tmp_project_v2)
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    result = runner.invoke(app, ["unlock"])
    assert result.exit_code == 1
    assert json.loads(result.output)["error"] == "gate_wrong_state"
