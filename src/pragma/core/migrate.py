"""v0.1 -> v0.2 manifest migrator.

Pure dict-to-dict transform. The CLI wrapper (cli/commands/migrate.py)
handles file IO and re-freezing.
"""

from __future__ import annotations

import copy
from typing import Any

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
