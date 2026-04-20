from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app


runner = CliRunner()


def test_full_hook_roundtrip(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0

    r = runner.invoke(
        app, ["hook", "session-start"],
        input=json.dumps({"session_id": "x", "source": "startup"}),
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert "LOCKED" in out["additionalContext"]

    r = runner.invoke(
        app, ["hook", "pre-tool-use"],
        input=json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/demo/thing.py"},
        }),
    )
    assert r.exit_code == 0
    assert json.loads(r.output)["permissionDecision"] == "deny"

    r = runner.invoke(
        app, ["hook", "pre-tool-use"],
        input=json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "tests/test_req_001.py"},
        }),
    )
    assert r.exit_code == 0
    assert json.loads(r.output)["permissionDecision"] == "allow"

    tdir = tmp_project_v2 / "tests"
    tdir.mkdir(exist_ok=True)
    (tdir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert False
            def test_req_001_sad(): assert False
        """),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["unlock"]).exit_code == 0

    (tmp_project_v2 / "src").mkdir(exist_ok=True)
    (tmp_project_v2 / "src" / "demo").mkdir(exist_ok=True)
    r = runner.invoke(
        app, ["hook", "pre-tool-use"],
        input=json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/demo/thing.py"},
        }),
    )
    assert r.exit_code == 0
    assert json.loads(r.output)["permissionDecision"] == "allow"

    (tmp_project_v2 / "src" / "demo" / "thing.py").write_text(
        "def thing(x):\n    return x + 1\n", encoding="utf-8",
    )
    r = runner.invoke(
        app, ["hook", "post-tool-use"],
        input=json.dumps({
            "tool_input": {"file_path": "src/demo/thing.py"},
        }),
    )
    assert r.exit_code == 0
    assert json.loads(r.output).get("decision") != "block"

    r = runner.invoke(
        app, ["hook", "stop"],
        input=json.dumps({"session_id": "x"}),
    )
    assert r.exit_code == 0
    result = json.loads(r.output)
    assert "continue" in result or "decision" in result
