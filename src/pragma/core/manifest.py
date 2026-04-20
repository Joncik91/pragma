"""Load, canonicalise, and hash the Logic Manifest.

Canonicalisation is deterministic (sorted-key JSON) because the hash
stored in pragma.lock.json is the integrity anchor — any reordering of
keys or whitespace on the YAML side must not produce a new hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from pragma.core.errors import (
    ManifestNotFound,
    ManifestSchemaError,
    ManifestSyntaxError,
)
from pragma.core.models import Manifest


def load_manifest(path: Path) -> Manifest:
    """Read, parse, and validate a pragma.yaml file.

    Raises ManifestNotFound / ManifestSyntaxError / ManifestSchemaError
    as typed errors so CLI commands emit a stable payload.
    """
    if not path.exists():
        raise ManifestNotFound(
            message=f"pragma.yaml not found at {path}",
            remediation="Run `pragma init --brownfield` to scaffold one.",
            context={"path": str(path)},
        )

    text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestSyntaxError(
            message=f"pragma.yaml is not valid YAML: {exc}",
            remediation=(
                "Fix the YAML syntax. A common cause is mis-indented "
                "permutations or unquoted special characters."
            ),
            context={"path": str(path)},
        ) from exc

    if raw is None or not isinstance(raw, dict):
        raise ManifestSchemaError(
            message="pragma.yaml must be a YAML mapping at the top level.",
            remediation="See docs/superpowers/specs/2026-04-20-pragma-v1-design.md §4.2.",
            context={"path": str(path)},
        )

    try:
        return Manifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestSchemaError(
            message=_first_error_message(exc),
            remediation=(
                "Fix the highlighted field. See manifest schema in spec §4."
            ),
            context={"path": str(path), "errors": exc.errors(include_url=False)},
        ) from exc


def canonicalise(manifest: Manifest) -> bytes:
    """Canonical JSON form used as the hash input and lockfile payload."""
    return json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def hash_manifest(manifest: Manifest) -> str:
    """Return `sha256:<hex>` over the canonical form."""
    digest = hashlib.sha256(canonicalise(manifest)).hexdigest()
    return f"sha256:{digest}"


def _first_error_message(exc: ValidationError) -> str:
    errs = exc.errors(include_url=False)
    if not errs:
        return "schema validation failed"
    first = errs[0]
    loc = ".".join(str(p) for p in first["loc"])
    return f"{loc}: {first['msg']}"
