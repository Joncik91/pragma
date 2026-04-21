"""End-to-end tests for `pragma doctor --emergency-unlock`.

Each test stands up a tmp brownfield repo, optionally mangles
`.pragma/state.json`, then runs the CLI in a subprocess and asserts on
stdout/return code. Subprocess-level testing matches the existing
doctor recovery suite and catches typer dispatch regressions the pure
unit tests would miss.
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


def _init_brownfield(cwd: Path) -> None:
    result = _run_pragma(cwd, "init", "--brownfield", "--name", "demo")
    assert result.returncode == 0, result.stderr
    result = _run_pragma(cwd, "freeze")
    assert result.returncode == 0, result.stderr


def _write_bricked_state(cwd: Path) -> None:
    """Schema-valid-enough JSON but referencing a bogus slice."""
    payload = {
        "version": 1,
        "active_slice": "BOGUS",
        "gate": "LOCKED",
        "manifest_hash": "sha256:" + "0" * 64,
        "slices": {
            "BOGUS": {
                "status": "in_progress",
                "gate": "LOCKED",
            }
        },
        "last_transition": None,
    }
    (cwd / ".pragma" / "state.json").write_text(json.dumps(payload), encoding="utf-8")


def _read_audit(cwd: Path) -> list[dict[str, object]]:
    path = cwd / ".pragma" / "audit.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_emergency_unlock_on_bricked_state(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    _write_bricked_state(tmp_path)

    audit_before = _read_audit(tmp_path)

    result = _run_pragma(
        tmp_path,
        "doctor",
        "--emergency-unlock",
        "--reason",
        "manual reset after migration",
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["action"] == "emergency_unlock"
    assert payload["previous_active_slice"] == "BOGUS"
    assert payload["reason"] == "manual reset after migration"

    # State now a valid default.
    from pragma.core.state import read_state

    state = read_state(tmp_path / ".pragma")
    assert state.version == 1
    assert state.active_slice is None
    assert state.gate is None
    assert state.slices == {}
    assert state.last_transition is None
    assert len(state.manifest_hash) >= len("sha256:") + 64

    # Audit line appended.
    audit_after = _read_audit(tmp_path)
    assert len(audit_after) == len(audit_before) + 1
    entry = audit_after[-1]
    assert entry["event"] == "emergency_unlock"
    assert entry["actor"] == "doctor"
    assert entry["slice"] == "BOGUS"
    assert entry["to_state"] is None
    assert entry["reason"] == "manual reset after migration"
    assert entry["context"]["previous_slice"] == "BOGUS"
    assert entry["context"]["previous_gate"] == "LOCKED"


def test_emergency_unlock_refuses_healthy_repo(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)

    result = _run_pragma(
        tmp_path,
        "doctor",
        "--emergency-unlock",
        "--reason",
        "unnecessary but still",
    )
    assert result.returncode == 1, (
        f"rc={result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    payload = json.loads(result.stdout)
    assert payload["error"] == "emergency_unlock_refused"
    assert payload["context"]["active_slice"] is None
    assert payload["context"]["gate"] is None
    assert "pragma slice activate" in payload["remediation"]


def test_emergency_unlock_requires_reason(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    _write_bricked_state(tmp_path)

    # No --reason at all.
    result = _run_pragma(tmp_path, "doctor", "--emergency-unlock")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "reason_required"

    # Whitespace-only --reason also rejected.
    result = _run_pragma(tmp_path, "doctor", "--emergency-unlock", "--reason", "   ")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "reason_required"


def test_emergency_unlock_unparseable_state(tmp_path: Path) -> None:
    _init_brownfield(tmp_path)
    (tmp_path / ".pragma" / "state.json").write_text("{not json", encoding="utf-8")

    result = _run_pragma(
        tmp_path,
        "doctor",
        "--emergency-unlock",
        "--reason",
        "state.json corrupted, resetting",
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["action"] == "emergency_unlock"
    assert payload["previous_active_slice"] is None

    # State regenerated and parses.
    from pragma.core.state import read_state

    state = read_state(tmp_path / ".pragma")
    assert state.active_slice is None
    assert state.gate is None

    # Audit line present with from_state=UNKNOWN.
    audit = _read_audit(tmp_path)
    entry = audit[-1]
    assert entry["event"] == "emergency_unlock"
    assert entry["from_state"] == "UNKNOWN"
    assert entry["reason"] == "state.json corrupted, resetting"
