"""`pragma doctor` — self-diagnostic + recovery-advice report.

In v0.1 doctor was a stub that dumped six booleans. v1.0 lifts it into a
real recovery tool: it still dumps the original state fields (for
backwards compatibility), and ADDITIONALLY appends a ``diagnostics:``
list — one entry per detected failure mode — each with a ``remediation``
string the user (or Claude Code) can execute verbatim.

doctor always exits zero in the standard mode. Diagnostics are
informational; the caller decides what to do next.

v1.0 also adds ``--emergency-unlock --reason "<why>"`` — the escape hatch
for a wedged gate. See `_handle_emergency_unlock` below.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma import __version__
from pragma.core.audit import append_audit
from pragma.core.errors import (
    EmergencyUnlockRefused,
    PragmaError,
    StateNotFound,
    StateSchemaError,
)
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.recovery import diagnose
from pragma.core.state import default_state, read_state, write_state

_FALLBACK_HASH = "sha256:" + "0" * 64


class _PriorGateState:
    """Classification of the pre-unlock state for audit + refusal checks."""

    __slots__ = ("previous_slice", "previous_gate", "from_state_label", "already_neutral")

    def __init__(
        self,
        *,
        previous_slice: str | None,
        previous_gate: str | None,
        from_state_label: str,
        already_neutral: bool,
    ) -> None:
        self.previous_slice = previous_slice
        self.previous_gate = previous_gate
        self.from_state_label = from_state_label
        self.already_neutral = already_neutral


def _classify_prior_state(pragma_dir: Path) -> _PriorGateState:
    """Classify pre-unlock state into already-neutral vs. needs-unlock.

    Three buckets:
      - already neutral (state absent, or parses with active_slice None)
      - parseable with an active slice (legitimate unlock target)
      - present but unparseable / schema-invalid (also a legit target)
    """
    try:
        state = read_state(pragma_dir)
    except StateNotFound:
        return _PriorGateState(
            previous_slice=None,
            previous_gate=None,
            from_state_label="UNKNOWN",
            already_neutral=True,
        )
    except StateSchemaError:
        return _PriorGateState(
            previous_slice=None,
            previous_gate=None,
            from_state_label="UNKNOWN",
            already_neutral=False,
        )
    return _PriorGateState(
        previous_slice=state.active_slice,
        previous_gate=state.gate,
        from_state_label=state.gate if state.gate is not None else "UNKNOWN",
        already_neutral=state.active_slice is None,
    )


def _reject_empty_reason() -> None:
    err = PragmaError(
        code="reason_required",
        message="--emergency-unlock requires --reason <non-empty text>.",
        remediation=(
            'Re-run with --reason "<why you\'re unlocking>"; the reason '
            "is appended to .pragma/audit.jsonl for posterity."
        ),
        context={},
    )
    typer.echo(err.to_json())
    raise typer.Exit(code=1)


def _reject_already_neutral() -> None:
    err = EmergencyUnlockRefused(
        message=(
            "Repo is already in a neutral state — no active slice, no gate. "
            "--emergency-unlock would be a no-op."
        ),
        remediation=(
            "Repo is already in a neutral state — run "
            "`pragma slice activate <id>` to start a slice, or inspect "
            ".pragma/audit.jsonl for history."
        ),
        context={"active_slice": None, "gate": None},
    )
    typer.echo(err.to_json())
    raise typer.Exit(code=1)


def _current_manifest_hash_or_fallback(cwd: Path) -> str:
    try:
        return hash_manifest(load_manifest(cwd / "pragma.yaml"))
    except PragmaError:
        return _FALLBACK_HASH


@trace("REQ-001")
def _handle_emergency_unlock(*, cwd: Path, reason: str) -> None:
    """Reset .pragma/state.json to neutral after logging the user's reason.

    Refuses when state parses cleanly AND no slice is active — in that
    case the repo is already in the "neutral" shape this command would
    produce, and firing would be a no-op audit spam.
    """
    stripped = reason.strip()
    if not stripped:
        _reject_empty_reason()

    pragma_dir = cwd / ".pragma"
    prior = _classify_prior_state(pragma_dir)
    if prior.already_neutral:
        _reject_already_neutral()

    manifest_hash = _current_manifest_hash_or_fallback(cwd)
    write_state(pragma_dir, default_state(manifest_hash=manifest_hash))

    append_audit(
        pragma_dir,
        event="emergency_unlock",
        actor="doctor",
        slice=prior.previous_slice,
        from_state=prior.from_state_label,
        to_state=None,
        reason=stripped,
        context={
            "previous_slice": prior.previous_slice,
            "previous_gate": prior.previous_gate,
        },
    )

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "action": "emergency_unlock",
                "previous_active_slice": prior.previous_slice,
                "reason": stripped,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


@trace("REQ-001")
def doctor(
    emergency_unlock: bool = typer.Option(
        False,
        "--emergency-unlock",
        help="Reset gate state to neutral after logging the reason.",
    ),
    reason: str = typer.Option(
        "",
        "--reason",
        help="Required with --emergency-unlock. Non-empty free-text.",
    ),
) -> None:
    """Print local install + project state as JSON, with recovery advice."""
    cwd = Path.cwd()

    if emergency_unlock:
        _handle_emergency_unlock(cwd=cwd, reason=reason)
        return

    diagnostics = diagnose(cwd)
    payload: dict[str, object] = {
        "ok": True,
        "pragma_version": __version__,
        "cwd": str(cwd),
        "manifest_exists": (cwd / "pragma.yaml").exists(),
        "lock_exists": (cwd / "pragma.lock.json").exists(),
        "pre_commit_config_exists": (cwd / ".pre-commit-config.yaml").exists(),
        "pragma_dir_exists": (cwd / ".pragma").exists(),
        "claude_settings_exists": (cwd / ".claude" / "settings.json").exists(),
        "diagnostics": diagnostics,
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
