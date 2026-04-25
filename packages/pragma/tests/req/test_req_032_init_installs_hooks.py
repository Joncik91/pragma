"""Red tests for REQ-032 — pragma init installs git hooks.

BUG-036. pragma init wrote .pre-commit-config.yaml but never ran
pre-commit install, so .git/hooks/ stayed unmodified. The shape-
checking commit-msg hook was therefore not enforced — a literal
README walkthrough produced an unenforced repo where bad commit
messages landed silently. Headline-promise breaking.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)


@trace("REQ-032")
def _assert_brownfield_installs_hooks(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init(tmp_project)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert result.exit_code == 0, result.stdout
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        path = tmp_project / ".git" / "hooks" / hook
        assert path.exists(), (
            f"pragma init --brownfield must install .git/hooks/{hook}; "
            f"only found {sorted((tmp_project / '.git' / 'hooks').glob('*'))!r}"
        )


@trace("REQ-032")
def _assert_greenfield_installs_hooks(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init(tmp_project)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(
        app,
        ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
    )
    assert result.exit_code == 0, result.stdout
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        path = tmp_project / ".git" / "hooks" / hook
        assert path.exists(), f"pragma init --greenfield must install .git/hooks/{hook}"


@trace("REQ-032")
def _assert_install_failure_does_not_block_init(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_project)
    monkeypatch.chdir(tmp_project)
    # Force pre-commit to fail by making the binary unfindable.
    monkeypatch.setenv("PATH", "/this/path/does/not/exist")
    result = runner.invoke(app, ["init", "--brownfield", "--name", "demo"])
    assert result.exit_code == 0, (
        f"init must succeed even when pre-commit is unavailable; got "
        f"exit_code={result.exit_code} stdout={result.stdout!r}"
    )
    payload = json.loads(result.stdout)
    assert payload.get("hooks_installed") is False, (
        f"payload must report hooks_installed=false when pre-commit cannot run; got {payload!r}"
    )


def test_req_032_brownfield_installs_hooks(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("brownfield_installs_hooks"):
        _assert_brownfield_installs_hooks(tmp_project, monkeypatch)


def test_req_032_greenfield_installs_hooks(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_installs_hooks"):
        _assert_greenfield_installs_hooks(tmp_project, monkeypatch)


def test_req_032_install_failure_does_not_block_init(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("install_failure_does_not_block_init"):
        _assert_install_failure_does_not_block_init(tmp_project, monkeypatch)


# Silence pyflakes on the unused sys import once tests stabilise.
assert sys is not None
