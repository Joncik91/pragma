from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.hooks.pre_tool_use import handle

runner = CliRunner()


def test_allow_when_no_active_slice(tmp_path: Path) -> None:
    out = handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/x.py"}},
        tmp_path,
    )
    assert out["permissionDecision"] == "allow"


def test_deny_when_locked_and_src_edit(
    monkeypatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/demo/thing.py"}},
        tmp_project_v2,
    )
    assert out["permissionDecision"] == "deny"
    assert "unlock" in out["remediation"].lower()
    assert "test_req_001" in out["remediation"]


def test_allow_when_locked_but_non_src_edit(
    monkeypatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "tests/test_x.py"}},
        tmp_project_v2,
    )
    assert out["permissionDecision"] == "allow"


def test_deny_when_unlocked_and_file_not_in_touches(
    monkeypatch,
    tmp_project_v2: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    tdir = tmp_project_v2 / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    out = handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/rogue.py"}},
        tmp_project_v2,
    )
    assert out["permissionDecision"] == "deny"
    assert "touches" in out["remediation"].lower()


def test_allow_when_unlocked_and_file_in_touches(
    monkeypatch,
    tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    tdir = tmp_project_v2 / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    out = handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/demo/thing.py"}},
        tmp_project_v2,
    )
    assert out["permissionDecision"] == "allow"
