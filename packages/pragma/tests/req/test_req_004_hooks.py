"""Dogfood: one function per REQ-004 permutation that pins v0.3 hooks + battery.

Each assertion is wrapped in a ``@trace("REQ-004")`` helper and the test
body enters ``set_permutation(...)`` so PIL scores the permutation as
``ok`` rather than ``mocked`` (KI-12).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.integrity import read_stored_hash, write_stored_hash
from pragma.hooks.post_tool_use import handle as post_tool_use_handle
from pragma.hooks.pre_tool_use import handle as pre_tool_use_handle
from pragma.hooks.session_start import handle as session_start_handle
from pragma.hooks.stop import handle as stop_handle

runner = CliRunner()


def _bootstrap(tmp_path: Path) -> Path:
    manifest = {
        "version": "2",
        "project": {
            "name": "demo",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "milestones": [
            {
                "id": "M01",
                "title": "T",
                "description": "T",
                "depends_on": [],
                "slices": [
                    {"id": "M01.S1", "title": "T", "description": "T", "requirements": ["REQ-001"]}
                ],
            }
        ],
        "requirements": [
            {
                "id": "REQ-001",
                "title": "T",
                "description": "T",
                "touches": ["src/demo/thing.py"],
                "permutations": [
                    {"id": "happy", "description": "happy", "expected": "success"},
                    {"id": "sad", "description": "sad", "expected": "reject"},
                ],
                "milestone": "M01",
                "slice": "M01.S1",
            }
        ],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".pragma").mkdir()
    return tmp_path


@trace("REQ-004")
def _assert_session_start_emits_context(project: Path) -> None:
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = session_start_handle({"session_id": "x", "source": "startup"}, project)
    assert out.get("continue") is True
    assert "additionalContext" in out
    assert "M01.S1" in out["additionalContext"]


@trace("REQ-004")
def _assert_pre_tool_use_denies_locked_src(project: Path) -> None:
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = pre_tool_use_handle(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/demo/thing.py"}},
        project,
    )
    assert out["permissionDecision"] == "deny"


@trace("REQ-004")
def _assert_pre_tool_use_allows_test_files(project: Path) -> None:
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = pre_tool_use_handle(
        {"tool_name": "Write", "tool_input": {"file_path": "tests/test_x.py"}},
        project,
    )
    assert out["permissionDecision"] == "allow"


@trace("REQ-004")
def _assert_post_tool_use_blocks_complexity(project: Path) -> None:
    src = project / "src" / "bad.py"
    branches = "\n    ".join(f"if x == {i}: return {i}" for i in range(11))
    src.write_text(f"def f(x):\n    {branches}\n    return -1\n", encoding="utf-8")
    out = post_tool_use_handle({"tool_input": {"file_path": "src/bad.py"}}, project)
    assert out["decision"] == "block"
    assert "complexity" in out["reason"].lower()


@trace("REQ-004")
def _assert_stop_blocks_on_verify_fail(project: Path) -> None:
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    raw = yaml.safe_load((project / "pragma.yaml").read_text(encoding="utf-8"))
    raw["requirements"][0]["permutations"].append(
        {"id": "extra", "description": "drift", "expected": "success"}
    )
    (project / "pragma.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False),
        encoding="utf-8",
    )
    out = stop_handle({"session_id": "x"}, project)
    assert out["decision"] == "block"


@trace("REQ-004")
def _assert_hooks_seal_writes_hash(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks":{}}', encoding="utf-8")
    r = runner.invoke(app, ["hooks", "seal"])
    assert r.exit_code == 0
    assert read_stored_hash(project / ".pragma") is not None


@trace("REQ-004")
def _assert_verify_integrity_rejects_drift(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks":{}}', encoding="utf-8")
    write_stored_hash(project / ".pragma", "sha256:" + "0" * 64)
    r = runner.invoke(app, ["verify", "integrity"])
    assert r.exit_code == 1


@trace("REQ-004")
def _assert_init_writes_v03_artifacts(project: Path) -> None:
    r = runner.invoke(app, ["init", "--brownfield", "--name", "d"])
    assert r.exit_code == 0
    settings = project / ".claude" / "settings.json"
    assert settings.exists()
    assert json.loads(settings.read_text())["hooks"]["SessionStart"] is not None
    assert read_stored_hash(project / ".pragma") is not None


def test_req_004_session_start_emits_context(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("session_start_emits_context"):
            _assert_session_start_emits_context(p)
    finally:
        monkeypatch.undo()


def test_req_004_pre_tool_use_denies_locked_src(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("pre_tool_use_denies_locked_src"):
            _assert_pre_tool_use_denies_locked_src(p)
    finally:
        monkeypatch.undo()


def test_req_004_pre_tool_use_allows_test_files(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("pre_tool_use_allows_test_files"):
            _assert_pre_tool_use_allows_test_files(p)
    finally:
        monkeypatch.undo()


def test_req_004_post_tool_use_blocks_complexity(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    with set_permutation("post_tool_use_blocks_complexity"):
        _assert_post_tool_use_blocks_complexity(p)


def test_req_004_stop_blocks_on_verify_fail(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("stop_blocks_on_verify_fail"):
            _assert_stop_blocks_on_verify_fail(p)
    finally:
        monkeypatch.undo()


def test_req_004_hooks_seal_writes_hash(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("hooks_seal_writes_hash"):
            _assert_hooks_seal_writes_hash(p)
    finally:
        monkeypatch.undo()


def test_req_004_verify_integrity_rejects_drift(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        with set_permutation("verify_integrity_rejects_drift"):
            _assert_verify_integrity_rejects_drift(p)
    finally:
        monkeypatch.undo()


def test_req_004_init_writes_v03_artifacts(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(tmp_path)
    try:
        with set_permutation("init_writes_v03_artifacts"):
            _assert_init_writes_v03_artifacts(tmp_path)
    finally:
        monkeypatch.undo()
