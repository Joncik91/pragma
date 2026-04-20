from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app


runner = CliRunner()


def test_hook_session_start(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(
        app, ["hook", "session-start"],
        input=json.dumps({"session_id": "x", "source": "startup"}),
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out.get("continue") is True


def test_hook_unknown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hook", "bogus"], input="{}")
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "unknown_hook_event"


def test_hook_missing_stdin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["hook", "session-start"], input="")
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "hook_input_missing"
