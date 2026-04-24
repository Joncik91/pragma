"""Red tests for REQ-029 — audit_orphan ignores non-slice events.

BUG-030. `pragma doctor` reported audit_orphan when audit.jsonl had
any line but state.slices was empty. Non-slice events (hooks_seal,
spans_cleaned) populated audit without being slice history, so a
fresh sandbox that had re-sealed its hash tripped the diagnostic
despite having a valid empty state.
"""

from __future__ import annotations

import json
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.core.recovery import diagnose


def _pragma_dir_with_audit_events(tmp_path: Path, events: list[dict]) -> None:
    """Bootstrap a minimal greenfield and manually seed audit + empty state.

    `diagnose()` short-circuits on fatal checks (no_manifest, hash_mismatch)
    so we must produce a manifest + freeze it before seeding the audit.
    """
    # Use the real init + freeze so hashes match; easier than computing
    # canonical hashes by hand here.
    import os

    from typer.testing import CliRunner

    from pragma.__main__ import app

    runner = CliRunner()
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert (
            runner.invoke(
                app,
                ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
            ).exit_code
            == 0
        )
    finally:
        os.chdir(cwd)

    pragma_dir = tmp_path / ".pragma"
    # Overwrite audit with exactly the events we want to probe.
    (pragma_dir / "audit.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )
    # Neutral state with empty slices — the shape that trips orphan.
    state_payload = json.loads((pragma_dir / "state.json").read_text(encoding="utf-8"))
    state_payload["active_slice"] = None
    state_payload["gate"] = None
    state_payload["slices"] = {}
    state_payload["last_transition"] = None
    (pragma_dir / "state.json").write_text(json.dumps(state_payload), encoding="utf-8")


@trace("REQ-029")
def _assert_hooks_seal_only_does_not_trip_orphan(tmp_path: Path) -> None:
    _pragma_dir_with_audit_events(
        tmp_path,
        [
            {
                "ts": "2026-04-24T22:00:00Z",
                "event": "hooks_seal",
                "actor": "operator",
                "slice": None,
                "from_state": None,
                "to_state": None,
                "reason": "Re-sealed settings.json hash.",
                "context": {},
            }
        ],
    )
    diagnostics = diagnose(tmp_path)
    codes = {d["code"] for d in diagnostics}
    assert "audit_orphan" not in codes, (
        f"audit_orphan must not fire for non-slice events; diagnostics={diagnostics!r}"
    )


@trace("REQ-029")
def _assert_slice_transition_without_state_does_trip(tmp_path: Path) -> None:
    _pragma_dir_with_audit_events(
        tmp_path,
        [
            {
                "ts": "2026-04-24T22:00:00Z",
                "event": "slice_activated",
                "actor": "cli",
                "slice": "M01.S1",
                "from_state": None,
                "to_state": "LOCKED",
                "reason": "pragma slice activate M01.S1",
                "context": {},
            }
        ],
    )
    diagnostics = diagnose(tmp_path)
    codes = {d["code"] for d in diagnostics}
    assert "audit_orphan" in codes, (
        f"audit_orphan must still fire when a slice-transition event exists "
        f"but state.slices is empty; diagnostics={diagnostics!r}"
    )


def test_req_029_hooks_seal_only_does_not_trip_orphan(tmp_path: Path) -> None:
    with set_permutation("hooks_seal_only_does_not_trip_orphan"):
        _assert_hooks_seal_only_does_not_trip_orphan(tmp_path)


def test_req_029_slice_transition_without_state_does_trip(tmp_path: Path) -> None:
    with set_permutation("slice_transition_without_state_does_trip"):
        _assert_slice_transition_without_state_does_trip(tmp_path)
