"""Dogfood: one function per REQ-003 permutation that pins v0.2 behaviour.

These are intentionally thin wrappers over the unit tests added in
tasks 4-14. Their purpose is to satisfy the unlock convention and
document the manifest's claims in executable form.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.audit import read_audit
from pragma.core.state import read_state


runner = CliRunner()


@pytest.fixture
def active_demo(monkeypatch: pytest.MonkeyPatch, tmp_project_v2: Path) -> Path:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    return tmp_project_v2


def test_req_003_activate_locks(active_demo: Path) -> None:
    state = read_state(active_demo / ".pragma")
    assert state.gate == "LOCKED"
    audit = read_audit(active_demo / ".pragma")
    assert audit[-1]["event"] == "slice_activated"


def test_req_003_unlock_requires_red_tests(active_demo: Path) -> None:
    r = runner.invoke(app, ["unlock"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "unlock_missing_tests"


def test_req_003_unlock_from_locked_with_red_tests(active_demo: Path) -> None:
    tdir = active_demo / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0


def test_req_003_complete_requires_green(active_demo: Path) -> None:
    tdir = active_demo / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    r = runner.invoke(app, ["slice", "complete"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "complete_tests_failing"


def test_req_003_complete_ships_when_green(active_demo: Path) -> None:
    tdir = active_demo / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert True\ndef test_req_001_sad(): assert True\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["slice", "complete"])
    assert r.exit_code == 0, r.output


def test_req_003_audit_append_only(active_demo: Path) -> None:
    before = len(read_audit(active_demo / ".pragma"))
    assert runner.invoke(app, ["slice", "cancel"]).exit_code == 0
    after = read_audit(active_demo / ".pragma")
    assert len(after) == before + 1
    assert after[-1]["event"] == "slice_cancelled"
