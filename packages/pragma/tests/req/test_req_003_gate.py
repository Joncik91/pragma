"""Dogfood: one function per REQ-003 permutation that pins v0.2 behaviour.

Each assertion is wrapped in a ``@trace("REQ-003")`` helper and the
test body enters ``set_permutation(...)`` so PIL scores the permutation
as ``ok`` rather than ``mocked`` (KI-12). The spans carry both
``pragma.logic_id=REQ-003`` and ``pragma.permutation=<id>``; the v1.0.2
aggregator requires both to match.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
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


@trace("REQ-003")
def _assert_activate_locks(project: Path) -> None:
    state = read_state(project / ".pragma")
    assert state.gate == "LOCKED"
    audit = read_audit(project / ".pragma")
    assert audit[-1]["event"] == "slice_activated"


@trace("REQ-003")
def _assert_unlock_requires_red_tests() -> None:
    r = runner.invoke(app, ["unlock"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "unlock_missing_tests"


@trace("REQ-003")
def _assert_unlock_from_locked_with_red_tests(project: Path) -> None:
    tdir = project / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0


@trace("REQ-003")
def _assert_complete_requires_green(project: Path) -> None:
    tdir = project / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        "def test_req_001_happy(): assert False\ndef test_req_001_sad(): assert False\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    r = runner.invoke(app, ["slice", "complete"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "complete_tests_failing"


@trace("REQ-003")
def _assert_complete_ships_when_green(project: Path) -> None:
    tdir = project / "tests"
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


@trace("REQ-003")
def _assert_audit_append_only(project: Path) -> None:
    before = len(read_audit(project / ".pragma"))
    assert runner.invoke(app, ["slice", "cancel"]).exit_code == 0
    after = read_audit(project / ".pragma")
    assert len(after) == before + 1
    assert after[-1]["event"] == "slice_cancelled"


def test_req_003_activate_locks(active_demo: Path) -> None:
    with set_permutation("activate_locks"):
        _assert_activate_locks(active_demo)


def test_req_003_unlock_requires_red_tests(active_demo: Path) -> None:
    with set_permutation("unlock_requires_red_tests"):
        _assert_unlock_requires_red_tests()


def test_req_003_unlock_from_locked_with_red_tests(active_demo: Path) -> None:
    with set_permutation("unlock_from_locked_with_red_tests"):
        _assert_unlock_from_locked_with_red_tests(active_demo)


def test_req_003_complete_requires_green(active_demo: Path) -> None:
    with set_permutation("complete_requires_green"):
        _assert_complete_requires_green(active_demo)


def test_req_003_complete_ships_when_green(active_demo: Path) -> None:
    with set_permutation("complete_ships_when_green"):
        _assert_complete_ships_when_green(active_demo)


def test_req_003_audit_append_only(active_demo: Path) -> None:
    with set_permutation("audit_append_only"):
        _assert_audit_append_only(active_demo)
