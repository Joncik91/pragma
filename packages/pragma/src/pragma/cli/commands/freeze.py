"""`pragma freeze` — regenerate pragma.lock.json from pragma.yaml."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma.core.errors import PragmaError, StateNotFound, StateSchemaError
from pragma.core.lockfile import write_lock
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.state import State, read_state, write_state


def _rebind_neutral_state_hash(pragma_dir: Path, new_hash: str) -> None:
    """BUG-032 / REQ-030: freeze rebinds state.manifest_hash when neutral.

    Only rebinds if state.json exists AND active_slice is None. During
    an active slice the stale hash is meaningful signal (the gate
    exists to catch mid-slice drift), so freeze leaves it alone.
    """
    try:
        state = read_state(pragma_dir)
    except (StateNotFound, StateSchemaError):
        return
    if state.active_slice is not None:
        return
    if state.manifest_hash == new_hash:
        return
    new_state = State(
        version=state.version,
        active_slice=state.active_slice,
        gate=state.gate,
        manifest_hash=new_hash,
        slices=state.slices,
        last_transition=state.last_transition,
    )
    write_state(pragma_dir, new_state)


@trace("REQ-001")
def freeze() -> None:
    """Read pragma.yaml, validate, write pragma.lock.json atomically."""
    cwd = Path.cwd()
    yaml_path = cwd / "pragma.yaml"
    lock_path = cwd / "pragma.lock.json"

    try:
        manifest = load_manifest(yaml_path)
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_lock(lock_path, manifest, now_iso=now_iso)
        _rebind_neutral_state_hash(cwd / ".pragma", hash_manifest(manifest))
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "wrote": "pragma.lock.json",
                "manifest_hash": hash_manifest(manifest),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
