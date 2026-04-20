"""`pragma verify manifest` — check pragma.yaml ↔ pragma.lock.json integrity."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pragma.core.errors import ManifestHashMismatch, PragmaError
from pragma.core.lockfile import read_lock
from pragma.core.manifest import hash_manifest, load_manifest

verify_app = typer.Typer(
    name="verify",
    help="Check invariants of the Pragma project.",
    no_args_is_help=True,
)


@verify_app.command(name="manifest")
def verify_manifest() -> None:
    """Fail loudly if pragma.yaml and pragma.lock.json disagree."""
    cwd = Path.cwd()
    try:
        manifest = load_manifest(cwd / "pragma.yaml")
        lock = read_lock(cwd / "pragma.lock.json")

        computed_hash = hash_manifest(manifest)
        if computed_hash != lock.manifest_hash:
            raise ManifestHashMismatch(
                message=(
                    "pragma.yaml has changed since the last `pragma freeze`. "
                    "The lockfile hash no longer matches the manifest."
                ),
                remediation=(
                    "Run `pragma freeze` to regenerate pragma.lock.json, "
                    "then stage both files and retry the commit."
                ),
                context={
                    "computed": computed_hash,
                    "lock": lock.manifest_hash,
                },
            )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "check": "manifest",
                "manifest_hash": lock.manifest_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
