"""Append-only audit log at `.pragma/audit.jsonl`.

Every gate transition, every unlock denial, every verify failure
appends one JSON line. The file is committed (it's evidence, not
session state). Writes are O_APPEND + fsync so a crash mid-write cannot
truncate an existing line.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pragma_sdk import trace

AUDIT_FILENAME = "audit.jsonl"


@trace("REQ-003")
def append_audit(
    pragma_dir: Path,
    *,
    event: str,
    actor: str,
    slice: str | None,
    from_state: str | None,
    to_state: str | None,
    reason: str,
    context: dict[str, Any] | None = None,
    now_iso: str | None = None,
) -> None:
    """Append one event entry. All fields serialised as sort_keys JSON."""
    pragma_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now_iso or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "actor": actor,
        "slice": slice,
        "from_state": from_state,
        "to_state": to_state,
        "reason": reason,
        "context": context or {},
    }
    line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"

    path = pragma_dir / AUDIT_FILENAME
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_audit(pragma_dir: Path) -> list[dict[str, Any]]:
    path = pragma_dir / AUDIT_FILENAME
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out
