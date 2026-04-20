"""Read and atomically write pragma.lock.json.

The lockfile is the machine-readable twin of pragma.yaml. It embeds the
fully-validated manifest plus a sha256 hash used as the integrity anchor
for `pragma verify manifest`. Writes are atomic (tempfile + rename) so a
crashed CLI never leaves a half-written lock on disk.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pragma.core.errors import LockNotFound, ManifestSchemaError
from pragma.core.manifest import hash_manifest
from pragma.core.models import Manifest

_LOCK_FILENAME = "pragma.lock.json"


class LockFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"]
    manifest_hash: str = Field(min_length=len("sha256:") + 64)
    generated_at: str
    manifest: Manifest


def write_lock(path: Path, manifest: Manifest, *, now_iso: str) -> None:
    """Atomically write pragma.lock.json.

    `now_iso` is injected rather than read from wall-clock so tests are
    deterministic and so downstream determinism guarantees (spec §7.4)
    are easy to satisfy later by passing the commit timestamp.
    """
    lock = LockFile(
        version="1",
        manifest_hash=hash_manifest(manifest),
        generated_at=now_iso,
        manifest=manifest,
    )
    payload = lock.model_dump_json(indent=2) + "\n"

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: tempfile in the same dir (so rename is atomic on POSIX),
    # then os.replace().
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{_LOCK_FILENAME}.tmp-", dir=str(parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup; don't mask the original error.
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def read_lock(path: Path) -> LockFile:
    """Load pragma.lock.json, returning a validated LockFile."""
    if not path.exists():
        raise LockNotFound(
            message=f"pragma.lock.json not found at {path}",
            remediation="Run `pragma freeze` to generate the lock from pragma.yaml.",
            context={"path": str(path)},
        )

    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestSchemaError(
            message=f"pragma.lock.json is not valid JSON: {exc}",
            remediation="Delete pragma.lock.json and re-run `pragma freeze`.",
            context={"path": str(path)},
        ) from exc

    try:
        return LockFile.model_validate(raw)
    except ValidationError as exc:
        raise ManifestSchemaError(
            message=f"pragma.lock.json schema invalid: {exc.errors(include_url=False)[0]['msg']}",
            remediation="Delete pragma.lock.json and re-run `pragma freeze`.",
            context={"path": str(path)},
        ) from exc
