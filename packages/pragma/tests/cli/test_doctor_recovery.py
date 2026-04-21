"""End-to-end tests for the v1.0 `pragma doctor` recovery engine.

Each test stands up a tmp directory in a failure shape, runs
``python -m pragma doctor`` in a subprocess, parses stdout as JSON, and
asserts the expected diagnostic code surfaces (or is absent, for the
healthy case). Subprocess-level testing is deliberate — doctor's contract
is the JSON it prints, and running the CLI for real catches any typer /
dispatch-layer regressions that a direct ``diagnose()`` unit test
wouldn't.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_pragma(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pragma", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _doctor(cwd: Path) -> dict[str, object]:
    result = _run_pragma(cwd, "doctor")
    assert result.returncode == 0, (
        f"doctor must always exit zero, got {result.returncode}. "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    return json.loads(result.stdout)


def _codes(payload: dict[str, object]) -> list[str]:
    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, list)
    return [d["code"] for d in diagnostics]  # type: ignore[index]


def _init_brownfield(cwd: Path) -> None:
    """Scaffold a valid brownfield repo + freeze its lock."""
    result = _run_pragma(cwd, "init", "--brownfield", "--name", "demo")
    assert result.returncode == 0, result.stderr
    result = _run_pragma(cwd, "freeze")
    assert result.returncode == 0, result.stderr


# --- Fatal branches ----------------------------------------------------


def test_doctor_no_manifest(tmp_path: Path) -> None:
    payload = _doctor(tmp_path)
    assert payload["manifest_exists"] is False
    codes = _codes(payload)
    assert "no_manifest" in codes
    # Fatal branches short-circuit — nothing else fires.
    assert len(codes) == 1
    entry = payload["diagnostics"][0]  # type: ignore[index]
    assert entry["severity"] == "fatal"
    assert "pragma init" in entry["remediation"]


def test_doctor_no_lock(tmp_path: Path) -> None:
    result = _run_pragma(tmp_path, "init", "--brownfield", "--name", "demo")
    assert result.returncode == 0
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert codes == ["no_lock"]
    entry = payload["diagnostics"][0]  # type: ignore[index]
    assert entry["severity"] == "fatal"
    assert "pragma freeze" in entry["remediation"]


def test_doctor_hash_mismatch(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    manifest = tmp_path / "pragma.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('name: "demo"', 'name: "drifted"'),
        encoding="utf-8",
    )
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert codes == ["hash_mismatch"]
    entry = payload["diagnostics"][0]  # type: ignore[index]
    assert entry["severity"] == "fatal"
    ctx = entry["context"]
    assert "manifest_hash" in ctx
    assert "lock_manifest_hash" in ctx
    assert ctx["manifest_hash"] != ctx["lock_manifest_hash"]


def test_doctor_lockfile_unparseable(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    (tmp_path / "pragma.lock.json").write_text("{ not json", encoding="utf-8")
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert codes == ["lockfile_unparseable"]
    entry = payload["diagnostics"][0]  # type: ignore[index]
    assert entry["severity"] == "fatal"
    assert "pragma freeze" in entry["remediation"]


# --- Warn branches -----------------------------------------------------


def test_doctor_no_pragma_dir(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    # Nuke .pragma/ after freeze so the lock survives but the dir is gone.
    pragma_dir = tmp_path / ".pragma"
    for child in pragma_dir.rglob("*"):
        if child.is_file():
            child.unlink()
    for child in sorted(pragma_dir.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()
    pragma_dir.rmdir()
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert "no_pragma_dir" in codes
    entry = next(
        d
        for d in payload["diagnostics"]  # type: ignore[attr-defined]
        if d["code"] == "no_pragma_dir"
    )
    assert entry["severity"] == "warn"


def test_doctor_stale_state(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    state = {
        "version": 1,
        "active_slice": None,
        "gate": None,
        "manifest_hash": "sha256:" + "0" * 64,
        "slices": {},
        "last_transition": None,
    }
    (tmp_path / ".pragma" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert "stale_state" in codes
    entry = next(
        d
        for d in payload["diagnostics"]  # type: ignore[attr-defined]
        if d["code"] == "stale_state"
    )
    assert entry["severity"] == "warn"
    ctx = entry["context"]
    assert ctx["state_manifest_hash"] == "sha256:" + "0" * 64
    assert ctx["state_manifest_hash"] != ctx["lock_manifest_hash"]


def test_doctor_claude_settings_mismatch(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    settings = tmp_path / ".claude" / "settings.json"
    # Tamper after init stored its hash.
    settings.write_text(settings.read_text() + "\n", encoding="utf-8")
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert "claude_settings_mismatch" in codes
    entry = next(
        d
        for d in payload["diagnostics"]  # type: ignore[attr-defined]
        if d["code"] == "claude_settings_mismatch"
    )
    assert entry["severity"] == "warn"
    assert "pragma init --force" in entry["remediation"]


def test_doctor_audit_orphan(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    pragma_dir = tmp_path / ".pragma"
    (pragma_dir / "audit.jsonl").write_text(
        '{"event":"unlock","actor":"pragma","slice":"S1",'
        '"from_state":"LOCKED","to_state":"UNLOCKED","reason":"test",'
        '"context":{},"ts":"2026-04-21T00:00:00Z"}\n',
        encoding="utf-8",
    )
    # state.json deliberately absent — this is the orphan scenario.
    assert not (pragma_dir / "state.json").exists()
    payload = _doctor(tmp_path)
    codes = _codes(payload)
    assert "audit_orphan" in codes
    entry = next(
        d
        for d in payload["diagnostics"]  # type: ignore[attr-defined]
        if d["code"] == "audit_orphan"
    )
    assert entry["severity"] == "warn"
    assert "--emergency-unlock" in entry["remediation"]


# --- Healthy + backwards-compat ---------------------------------------


def test_doctor_healthy(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    payload = _doctor(tmp_path)
    assert payload["diagnostics"] == []


def test_doctor_backwards_compat_fields(tmp_path: Path) -> None:
    """All six v0.1 payload keys must remain in the JSON."""
    payload = _doctor(tmp_path)
    for key in (
        "ok",
        "pragma_version",
        "cwd",
        "manifest_exists",
        "lock_exists",
        "pre_commit_config_exists",
    ):
        assert key in payload, f"v0.1 payload key {key!r} missing from doctor output"
