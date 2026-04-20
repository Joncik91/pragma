"""`pragma migrate` — upgrade pragma.yaml from v1 to v2."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
import yaml

from pragma.core.errors import ManifestNotFound, ManifestSchemaError, PragmaError
from pragma.core.lockfile import write_lock
from pragma.core.manifest import hash_manifest
from pragma.core.migrate import migrate_v1_to_v2
from pragma.core.models import Manifest


def migrate(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would change without writing pragma.yaml or pragma.lock.json.",
    ),
) -> None:
    """Upgrade pragma.yaml from v1 to v2. Idempotent; safe to re-run."""
    cwd = Path.cwd()
    yaml_path = cwd / "pragma.yaml"

    if not yaml_path.exists():
        err: PragmaError = ManifestNotFound(
            message=f"pragma.yaml not found at {yaml_path}",
            remediation="Run `pragma init --brownfield` first.",
            context={"path": str(yaml_path)},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1)

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        err = ManifestSchemaError(
            message=f"pragma.yaml is not valid YAML: {exc}",
            remediation="Fix the YAML syntax and re-run.",
            context={"path": str(yaml_path)},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1) from None

    current_version = raw.get("version") if isinstance(raw, dict) else None
    if current_version == "2":
        typer.echo(
            json.dumps(
                {
                    "ok": True,
                    "migrated": False,
                    "reason": "already_v2",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return

    try:
        upgraded = migrate_v1_to_v2(raw)
    except ValueError as exc:
        err = ManifestSchemaError(
            message=str(exc),
            remediation="Only v1 manifests can be migrated. Inspect the version: field.",
            context={"version": current_version},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1) from None

    try:
        manifest = Manifest.model_validate(upgraded)
    except Exception as exc:
        err = ManifestSchemaError(
            message=f"migrated manifest failed v2 schema validation: {exc}",
            remediation=(
                "This is likely a bug in `pragma migrate`. Report it with "
                "a copy of pragma.yaml. Run with --dry-run to inspect the "
                "would-be output."
            ),
            context={"path": str(yaml_path)},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1) from None

    if dry_run:
        typer.echo(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "from_version": current_version,
                    "to_version": "2",
                    "would_write": str(yaml_path),
                    "slices_created": ["M00.S0"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return

    try:
        yaml_path.write_text(
            yaml.safe_dump(upgraded, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )

        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_lock(cwd / "pragma.lock.json", manifest, now_iso=now_iso)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "migrated": True,
                "from_version": current_version,
                "to_version": "2",
                "slices_created": ["M00.S0"],
                "manifest_hash": hash_manifest(manifest),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
