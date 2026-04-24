"""Red tests for REQ-026 — hooks verify drift semantics.

BUG-029. `pragma hooks verify` returned `ok=true` + exit 0 when the
integrity hash detected tampering. Downstream CI / pre-push scripts
that check the `ok` field treated drift as success. `pragma verify
integrity` already had the strict contract (ok=false, exit 1);
hooks verify was the inconsistent surface.

Fix: drift emits `ok=false` + exit 1. Other states (sealed,
not_sealed, no_settings) remain ok=true + exit 0.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _bootstrap_sealed_project(tmp_project: Path) -> None:
    """greenfield init scaffolds settings.json and seals the hash."""
    import os

    cwd = Path.cwd()
    try:
        os.chdir(tmp_project)
        assert (
            runner.invoke(
                app,
                ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
            ).exit_code
            == 0
        )
    finally:
        os.chdir(cwd)


@trace("REQ-026")
def _assert_drifted_is_ok_false_and_exit_1(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sealed_project(tmp_project)
    monkeypatch.chdir(tmp_project)
    # Tamper.
    settings = tmp_project / ".claude" / "settings.json"
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["_tampered"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["hooks", "verify"])
    assert result.exit_code == 1, (
        f"hooks verify must exit 1 on drift; got {result.exit_code} stdout={result.stdout!r}"
    )
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is False, f"hooks verify must set ok=false on drift; got {parsed!r}"
    assert parsed["integrity"] == "drifted"


@trace("REQ-026")
def _assert_sealed_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sealed_project(tmp_project)
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(app, ["hooks", "verify"])
    assert result.exit_code == 0, (
        f"hooks verify must exit 0 when sealed; got {result.exit_code} stdout={result.stdout!r}"
    )
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["integrity"] == "sealed"


@trace("REQ-026")
def _assert_not_sealed_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sealed_project(tmp_project)
    monkeypatch.chdir(tmp_project)
    # Remove the stored hash — settings.json is present but not sealed.
    (tmp_project / ".pragma" / "claude-settings.hash").unlink()
    result = runner.invoke(app, ["hooks", "verify"])
    assert result.exit_code == 0, (
        f"hooks verify must exit 0 when not_sealed; got {result.exit_code}"
    )
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["integrity"] == "not_sealed"


@trace("REQ-026")
def _assert_no_settings_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sealed_project(tmp_project)
    monkeypatch.chdir(tmp_project)
    # Remove settings entirely — the command should report no_settings.
    shutil.rmtree(tmp_project / ".claude")
    result = runner.invoke(app, ["hooks", "verify"])
    assert result.exit_code == 0, (
        f"hooks verify must exit 0 when settings is absent; got {result.exit_code}"
    )
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["integrity"] == "no_settings"


def test_req_026_drifted_is_ok_false_and_exit_1(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("drifted_is_ok_false_and_exit_1"):
        _assert_drifted_is_ok_false_and_exit_1(tmp_project, monkeypatch)


def test_req_026_sealed_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("sealed_is_ok_true_and_exit_0"):
        _assert_sealed_is_ok_true_and_exit_0(tmp_project, monkeypatch)


def test_req_026_not_sealed_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("not_sealed_is_ok_true_and_exit_0"):
        _assert_not_sealed_is_ok_true_and_exit_0(tmp_project, monkeypatch)


def test_req_026_no_settings_is_ok_true_and_exit_0(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("no_settings_is_ok_true_and_exit_0"):
        _assert_no_settings_is_ok_true_and_exit_0(tmp_project, monkeypatch)
