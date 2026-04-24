"""Red tests for REQ-012 - slice cancel resets state to fully neutral.

BUG-016: `pragma slice cancel` only nulled `active_slice` and `gate` but
left the previous `manifest_hash` in state. If the manifest was
rewritten between activate and cancel, verify gate failed with
gate_hash_drift after cancel, and doctor --emergency-unlock refused
("already neutral"). v1.0.6: cancel rebinds state.manifest_hash to the
current lock's hash so state is truly neutral after cancel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.state import read_state

runner = CliRunner()


def _init_and_activate(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Set up a brownfield project with one requirement activated."""
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "spec",
                "add-requirement",
                "--id",
                "REQ-001",
                "--title",
                "Example requirement",
                "--description",
                "Placeholder",
                "--touches",
                "src/example.py",
                "--permutation",
                "happy|happy path|success",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    # Brownfield init writes a v1 manifest; slices require v2.
    assert runner.invoke(app, ["migrate"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M00.S0"]).exit_code == 0
    return _current_lock_hash(tmp_project)


def _current_lock_hash(project: Path) -> str:
    payload = json.loads((project / "pragma.lock.json").read_text(encoding="utf-8"))
    hash_value = payload["manifest_hash"]
    assert isinstance(hash_value, str)
    return hash_value


def _rewrite_manifest_and_freeze(project: Path) -> str:
    """Mutate the manifest so the lock hash changes. Return the new hash."""
    yaml_path = project / "pragma.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    # Append a trailing vision field — benign content change that
    # flips the canonical hash.
    yaml_path.write_text(text + '\nvision: "changed after activate"\n', encoding="utf-8")
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    return _current_lock_hash(project)


@trace("REQ-012")
def _assert_cancel_rebinds_to_current_lock_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_hash = _init_and_activate(tmp_project, monkeypatch)
    new_hash = _rewrite_manifest_and_freeze(tmp_project)
    assert old_hash != new_hash
    assert runner.invoke(app, ["slice", "cancel"]).exit_code == 0
    state = read_state(tmp_project / ".pragma")
    assert state.manifest_hash == new_hash, (
        f"cancel must rebind state.manifest_hash to the current lock hash "
        f"({new_hash!r}); got {state.manifest_hash!r}"
    )


@trace("REQ-012")
def _assert_cancel_then_verify_gate_passes(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_and_activate(tmp_project, monkeypatch)
    _rewrite_manifest_and_freeze(tmp_project)
    assert runner.invoke(app, ["slice", "cancel"]).exit_code == 0
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 0, (
        f"verify gate must pass after cancel on a rewritten manifest; stdout={result.stdout!r}"
    )


def test_req_012_cancel_rebinds_to_current_lock_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("cancel_rebinds_to_current_lock_hash"):
        _assert_cancel_rebinds_to_current_lock_hash(tmp_project, monkeypatch)


def test_req_012_cancel_then_verify_gate_passes(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("cancel_then_verify_gate_passes"):
        _assert_cancel_then_verify_gate_passes(tmp_project, monkeypatch)
