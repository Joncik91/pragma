"""Manifest schema migrators.

Each migrator is a pure dict-to-dict transform. The CLI wrapper
(``cli/commands/migrate.py``) handles file IO and re-freezing.

v2 stays current at v1.0 — the milestone/slice hierarchy added in v0.2
is what greenfield authors into place. ``migrate_to_current`` is the
caller-facing entry point; it dispatches based on the manifest's
``version:`` field and is a no-op on v2 input. Future schema bumps
(v3, v4, ...) slot in a new ``migrate_vN_to_vN_plus_one`` helper and a
new branch inside ``migrate_to_current``; callers keep the same API.
"""

from __future__ import annotations

import copy
from typing import Any

CURRENT_SCHEMA_VERSION = "2"

_IMPLICIT_MILESTONE_ID = "M00"
_IMPLICIT_SLICE_ID = "M00.S0"


def migrate_v1_to_v2(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict upgraded from v1 to v2. Idempotent on v2 input."""
    if manifest.get("version") == "2":
        return manifest

    if manifest.get("version") != "1":
        raise ValueError(
            f"unexpected manifest version {manifest.get('version')!r}; "
            "only v1 can be migrated to v2"
        )

    out = copy.deepcopy(manifest)
    out["version"] = "2"

    requirements = out.get("requirements", [])
    req_ids = [r["id"] for r in requirements]

    out["milestones"] = [
        {
            "id": _IMPLICIT_MILESTONE_ID,
            "title": "Implicit brownfield milestone",
            "description": (
                "Auto-created by `pragma migrate` to wrap pre-v0.2 flat requirements. "
                "Safe to rename when the project grows real milestones."
            ),
            "depends_on": [],
            "slices": [
                {
                    "id": _IMPLICIT_SLICE_ID,
                    "title": "Implicit brownfield slice",
                    "description": (
                        "Auto-created by `pragma migrate`. All pre-v0.2 requirements "
                        "live here until the user carves real slices."
                    ),
                    "requirements": req_ids,
                }
            ],
        }
    ]

    for req in requirements:
        req["milestone"] = _IMPLICIT_MILESTONE_ID
        req["slice"] = _IMPLICIT_SLICE_ID

    return out


def migrate_to_current(manifest: dict[str, Any]) -> dict[str, Any]:
    """Bring ``manifest`` up to ``CURRENT_SCHEMA_VERSION``.

    Dispatches based on the manifest's ``version:`` field. v1 → v2 via
    ``migrate_v1_to_v2``; v2 is a no-op. Raises ``ValueError`` on
    unknown versions so a stale pragma binary cannot silently misread
    a future schema.
    """
    version = manifest.get("version")
    if version == CURRENT_SCHEMA_VERSION:
        return manifest
    if version == "1":
        return migrate_v1_to_v2(manifest)
    raise ValueError(
        f"unknown manifest version {version!r}; current schema is "
        f"v{CURRENT_SCHEMA_VERSION}. Upgrade pragma itself if this is a newer schema."
    )
