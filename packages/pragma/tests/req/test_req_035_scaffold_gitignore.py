"""Red tests for REQ-035 — scaffolded .gitignore covers cache + state.

BUG-042. Round-8 README walkthrough found scaffolded .gitignore only
had .pragma/spans/ and .pragma/pytest-junit.xml. The user's first
git add -A then staged .pragma/state.json (machine-local gate
state), .pragma/state.json.lock (flock), and __pycache__/ files.
ruff-format reformats the .pyc paths; pytest modify-detection
blocks the commit. Mysterious to a first-run user.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mode: str) -> str:
    """Run init in a fresh sub-dir per mode so we never re-init."""
    sub = tmp_path / f"sub_{mode}"
    sub.mkdir()
    monkeypatch.chdir(sub)
    cmd = ["init", f"--{mode}", "--name", "demo"]
    if mode == "greenfield":
        cmd += ["--language", "python"]
    result = runner.invoke(app, cmd)
    assert result.exit_code == 0, result.stdout
    return (sub / ".gitignore").read_text(encoding="utf-8")


@trace("REQ-035")
def _assert_ignores_state_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for mode in ("brownfield", "greenfield"):
        gitignore = _scaffold(tmp_path, monkeypatch, mode=mode)
        assert ".pragma/state.json" in gitignore, (
            f"({mode}) scaffolded .gitignore must list .pragma/state.json; got:\n{gitignore!r}"
        )


@trace("REQ-035")
def _assert_ignores_state_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for mode in ("brownfield", "greenfield"):
        gitignore = _scaffold(tmp_path, monkeypatch, mode=mode)
        assert ".pragma/state.json.lock" in gitignore, (
            f"({mode}) scaffolded .gitignore must list .pragma/state.json.lock; got:\n{gitignore!r}"
        )


@trace("REQ-035")
def _assert_ignores_pycache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for mode in ("brownfield", "greenfield"):
        gitignore = _scaffold(tmp_path, monkeypatch, mode=mode)
        assert "__pycache__/" in gitignore, (
            f"({mode}) scaffolded .gitignore must list __pycache__/; got:\n{gitignore!r}"
        )
        assert "*.pyc" in gitignore, (
            f"({mode}) scaffolded .gitignore must list *.pyc; got:\n{gitignore!r}"
        )


def test_req_035_ignores_state_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("ignores_state_json"):
        _assert_ignores_state_json(tmp_path, monkeypatch)


def test_req_035_ignores_state_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("ignores_state_lock"):
        _assert_ignores_state_lock(tmp_path, monkeypatch)


def test_req_035_ignores_pycache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("ignores_pycache"):
        _assert_ignores_pycache(tmp_path, monkeypatch)
