from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
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


def test_req_004_session_start_emits_context(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        assert runner.invoke(app, ["freeze"]).exit_code == 0
        assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
        out = session_start_handle({"session_id": "x", "source": "startup"}, p)
        assert out.get("continue") is True
        assert "additionalContext" in out
        assert "M01.S1" in out["additionalContext"]
    finally:
        monkeypatch.undo()


def test_req_004_pre_tool_use_denies_locked_src(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        assert runner.invoke(app, ["freeze"]).exit_code == 0
        assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
        out = pre_tool_use_handle(
            {"tool_name": "Edit", "tool_input": {"file_path": "src/demo/thing.py"}},
            p,
        )
        assert out["permissionDecision"] == "deny"
    finally:
        monkeypatch.undo()


def test_req_004_pre_tool_use_allows_test_files(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        assert runner.invoke(app, ["freeze"]).exit_code == 0
        assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
        out = pre_tool_use_handle(
            {"tool_name": "Write", "tool_input": {"file_path": "tests/test_x.py"}},
            p,
        )
        assert out["permissionDecision"] == "allow"
    finally:
        monkeypatch.undo()


def test_req_004_post_tool_use_blocks_complexity(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    src = p / "src" / "bad.py"
    branches = "\n    ".join(f"if x == {i}: return {i}" for i in range(11))
    src.write_text(f"def f(x):\n    {branches}\n    return -1\n", encoding="utf-8")
    out = post_tool_use_handle({"tool_input": {"file_path": "src/bad.py"}}, p)
    assert out["decision"] == "block"
    assert "complexity" in out["reason"].lower()


def test_req_004_stop_blocks_on_verify_fail(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        assert runner.invoke(app, ["freeze"]).exit_code == 0
        import yaml

        raw = yaml.safe_load((p / "pragma.yaml").read_text(encoding="utf-8"))
        raw["requirements"][0]["permutations"].append(
            {"id": "extra", "description": "drift", "expected": "success"}
        )
        (p / "pragma.yaml").write_text(
            yaml.safe_dump(raw, sort_keys=False),
            encoding="utf-8",
        )
        out = stop_handle({"session_id": "x"}, p)
        assert out["decision"] == "block"
    finally:
        monkeypatch.undo()


def test_req_004_hooks_seal_writes_hash(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        settings = p / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"hooks":{}}', encoding="utf-8")
        r = runner.invoke(app, ["hooks", "seal"])
        assert r.exit_code == 0
        assert read_stored_hash(p / ".pragma") is not None
    finally:
        monkeypatch.undo()


def test_req_004_verify_integrity_rejects_drift(tmp_path: Path) -> None:
    p = _bootstrap(tmp_path)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(p)
    try:
        settings = p / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"hooks":{}}', encoding="utf-8")
        write_stored_hash(p / ".pragma", "sha256:" + "0" * 64)
        r = runner.invoke(app, ["verify", "integrity"])
        assert r.exit_code == 1
    finally:
        monkeypatch.undo()


def test_req_004_init_writes_v03_artifacts(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(tmp_path)
    try:
        r = runner.invoke(app, ["init", "--brownfield", "--name", "d"])
        assert r.exit_code == 0
        settings = tmp_path / ".claude" / "settings.json"
        assert settings.exists()
        assert json.loads(settings.read_text())["hooks"]["SessionStart"] is not None
        assert read_stored_hash(tmp_path / ".pragma") is not None
    finally:
        monkeypatch.undo()
