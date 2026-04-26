"""Red tests for REQ-043 — `pragma start` one-command orchestrator.

v0.2.0 friction reduction. Today the greenfield bootstrap is five
commands (init → write problem.md → plan-greenfield → freeze →
slice activate). Each step is mechanical; none requires human
judgment between them. `pragma start "<intent>"` orchestrates all
five so the user (or a Claude Code plugin) lands at gate=LOCKED
in one call.

Behavior:
- Auto-detect greenfield (empty cwd) vs brownfield (existing code).
- Greenfield: init --greenfield, write docs/problem.md from the
  intent, plan-greenfield, freeze, activate M01.S1.
- Brownfield: init --brownfield, no problem.md, no plan-greenfield;
  user is expected to add-requirement separately, but the slice is
  already there (M00.S0) so activate it.
- Refuse cleanly when pragma.yaml already exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


@trace("REQ-043")
def _assert_greenfield_one_command_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["start", "User can log in with email and password"])
    assert result.exit_code == 0, f"pragma start must succeed; got:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "greenfield"
    assert payload["gate"] == "LOCKED"
    assert payload["slice"] == "M01.S1"
    # Manifest exists, has at least REQ-001, lock matches.
    assert (tmp_path / "pragma.yaml").exists()
    assert (tmp_path / "pragma.lock.json").exists()
    assert (tmp_path / "docs" / "problem.md").exists()
    raw = yaml.safe_load((tmp_path / "pragma.yaml").read_text(encoding="utf-8"))
    assert raw["version"] == "2"
    assert any(r["id"] == "REQ-001" for r in raw["requirements"])
    # State: gate is LOCKED on M01.S1.
    state = json.loads((tmp_path / ".pragma" / "state.json").read_text(encoding="utf-8"))
    assert state["active_slice"] == "M01.S1"
    assert state["gate"] == "LOCKED"


@trace("REQ-043")
def _assert_brownfield_one_command_adopt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate an existing repo: a src file + a git repo with one commit.
    import subprocess

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "existing.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", "add", "-A"],
        cwd=str(tmp_path),
        check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=str(tmp_path),
        check=True,
    )

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["start", "Wrap existing code in pragma"])
    assert result.exit_code == 0, f"pragma start must succeed; got:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "brownfield"
    assert payload["gate"] == "LOCKED"
    assert payload["slice"] == "M00.S0"


@trace("REQ-043")
def _assert_refuses_when_already_initialised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # First start succeeds.
    runner.invoke(app, ["start", "first feature"])
    # Second start refuses cleanly.
    result = runner.invoke(app, ["start", "another feature"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "already_initialised", (
        f"second start must refuse with already_initialised; got:\n{result.stdout}"
    )


def test_req_043_greenfield_one_command_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_one_command_bootstrap"):
        _assert_greenfield_one_command_bootstrap(tmp_path, monkeypatch)


def test_req_043_brownfield_one_command_adopt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("brownfield_one_command_adopt"):
        _assert_brownfield_one_command_adopt(tmp_path, monkeypatch)


def test_req_043_refuses_when_already_initialised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("refuses_when_already_initialised"):
        _assert_refuses_when_already_initialised(tmp_path, monkeypatch)
