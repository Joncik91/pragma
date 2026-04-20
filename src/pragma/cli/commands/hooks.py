from __future__ import annotations

import json
from pathlib import Path

import typer

from pragma.core.audit import append_audit
from pragma.core.errors import PragmaError, SettingsNotFoundError
from pragma.core.integrity import (
    compute_settings_hash,
    read_stored_hash,
    verify_settings_integrity,
    write_stored_hash,
)

hooks_app = typer.Typer(
    name="hooks",
    help="Seal, verify, and inspect .claude/settings.json integrity.",
    no_args_is_help=True,
)


def _resolve_settings(cwd: Path) -> Path:
    return cwd / ".claude" / "settings.json"


@hooks_app.command(name="seal")
def seal() -> None:
    cwd = Path.cwd()
    settings = _resolve_settings(cwd)
    if not settings.exists():
        raise typer.Exit(
            SettingsNotFoundError(
                message=".claude/settings.json not found.",
                remediation="Run this from a project with a .claude directory.",
            ).to_json()
        )
    hash_value = compute_settings_hash(settings)
    pragma_dir = cwd / ".pragma"
    write_stored_hash(pragma_dir, hash_value)
    append_audit(
        pragma_dir,
        event="hooks_seal",
        actor="operator",
        slice=None,
        from_state=None,
        to_state=None,
        reason="Re-sealed settings.json hash.",
    )
    typer.echo(
        json.dumps(
            {"ok": True, "hash": hash_value},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


@hooks_app.command(name="verify")
def verify() -> None:
    cwd = Path.cwd()
    settings = _resolve_settings(cwd)
    pragma_dir = cwd / ".pragma"
    if not settings.exists():
        typer.echo(
            json.dumps(
                {"ok": True, "integrity": "no_settings"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return
    result = verify_settings_integrity(settings, pragma_dir)
    if result is None:
        typer.echo(
            json.dumps(
                {"ok": True, "integrity": "not_sealed"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    elif result:
        typer.echo(
            json.dumps(
                {"ok": True, "integrity": "sealed"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        typer.echo(
            json.dumps(
                {"ok": True, "integrity": "drifted"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )


@hooks_app.command(name="show")
def show() -> None:
    cwd = Path.cwd()
    settings = _resolve_settings(cwd)
    pragma_dir = cwd / ".pragma"
    if not settings.exists():
        raise typer.Exit(
            SettingsNotFoundError(
                message=".claude/settings.json not found.",
                remediation="Run this from a project with a .claude directory.",
            ).to_json()
        )
    payload = json.loads(settings.read_text(encoding="utf-8"))
    stored = read_stored_hash(pragma_dir)
    if stored is None:
        integrity = "not_sealed"
    elif verify_settings_integrity(settings, pragma_dir):
        integrity = "sealed"
    else:
        integrity = "drifted"
    typer.echo(
        json.dumps(
            {"ok": True, "settings": payload, "integrity": integrity},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
