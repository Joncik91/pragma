"""`pragma freeze` — regenerate pragma.lock.json from pragma.yaml."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from pragma.core.errors import PragmaError
from pragma.core.lockfile import write_lock
from pragma.core.manifest import hash_manifest, load_manifest


def freeze() -> None:
    """Read pragma.yaml, validate, write pragma.lock.json atomically."""
    cwd = Path.cwd()
    yaml_path = cwd / "pragma.yaml"
    lock_path = cwd / "pragma.lock.json"

    try:
        manifest = load_manifest(yaml_path)
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_lock(lock_path, manifest, now_iso=now_iso)
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
