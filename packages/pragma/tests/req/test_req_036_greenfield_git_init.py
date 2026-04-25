"""Red tests for REQ-036 — greenfield init bootstraps the git repo.

BUG-044. Round-11 README walkthrough found that `mkdir demo && cd demo
&& pragma init --greenfield` produces `hooks_installed: false`. Reason:
`pre-commit install` silently no-ops without `.git/`, so the gate the
README advertises is not actually wired. Fix - greenfield runs
`git init -q` when no repo exists. Brownfield is unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


@trace("REQ-036")
def _assert_git_inited_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_path / "fresh"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert not (sub / ".git").exists()
    result = runner.invoke(app, ["init", "--greenfield", "--name", "demo", "--language", "python"])
    assert result.exit_code == 0, result.stdout
    assert (sub / ".git").exists(), "greenfield init should `git init -q` when no repo"


@trace("REQ-036")
def _assert_existing_git_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_path / "existing"
    sub.mkdir()
    git_dir = sub / ".git"
    git_dir.mkdir()
    sentinel = git_dir / "sentinel.txt"
    sentinel.write_text("preexisting", encoding="utf-8")
    monkeypatch.chdir(sub)
    result = runner.invoke(app, ["init", "--greenfield", "--name", "demo", "--language", "python"])
    assert result.exit_code == 0, result.stdout
    assert sentinel.exists() and sentinel.read_text(encoding="utf-8") == "preexisting", (
        "greenfield must not clobber an existing .git"
    )


def test_req_036_greenfield_inits_git_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_inits_git_when_absent"):
        _assert_git_inited_when_absent(tmp_path, monkeypatch)


def test_req_036_greenfield_leaves_existing_git_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_leaves_existing_git_alone"):
        _assert_existing_git_left_alone(tmp_path, monkeypatch)
