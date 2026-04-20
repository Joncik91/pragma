from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.gate import unlock_transition
from pragma.core.state import read_state, write_state


runner = CliRunner()


def _bootstrap_activated(tmp_project_v2: Path) -> None:
    (tmp_project_v2 / "tests").mkdir(exist_ok=True)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0


def test_complete_without_unlock_rejects(
    monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _bootstrap_activated(tmp_project_v2)
    result = runner.invoke(app, ["slice", "complete"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "gate_wrong_state"


def test_complete_skip_tests_from_locked_still_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _bootstrap_activated(tmp_project_v2)
    result = runner.invoke(app, ["slice", "complete", "--skip-tests"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "gate_wrong_state"


def _unlock_directly(project_dir: Path) -> None:
    pragma_dir = project_dir / ".pragma"
    state = read_state(pragma_dir)
    new_state, _ = unlock_transition(state, now_iso="2026-01-01T00:00:00Z")
    write_state(pragma_dir, new_state)


def test_complete_with_failing_tests_rejects(
    monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _bootstrap_activated(tmp_project_v2)
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert False
            def test_req_001_sad(): assert False
        """),
        encoding="utf-8",
    )
    _unlock_directly(tmp_project_v2)

    result = runner.invoke(app, ["slice", "complete"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "complete_tests_failing"


def test_complete_with_green_tests_ships(
    monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    _bootstrap_activated(tmp_project_v2)
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert False
            def test_req_001_sad(): assert False
        """),
        encoding="utf-8",
    )
    _unlock_directly(tmp_project_v2)

    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert True
            def test_req_001_sad(): assert True
        """),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["slice", "complete"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["status"] == "shipped"
