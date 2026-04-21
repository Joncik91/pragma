"""`pragma doctor` — self-diagnostic report.

v0.1 is a STUB. It prints the state a user / Claude Code would need to
triage a broken Pragma setup: pragma version, cwd, which files exist.
v0.2 adds gate-state inspection; v0.3 adds .claude/settings.json hash
verification; v1.0 adds emergency-unlock. Do not let the shape of this
stub drift in v0.1 — downstream versions build on the payload keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pragma import __version__


def doctor() -> None:
    """Print local install + project state as JSON."""
    cwd = Path.cwd()
    payload = {
        "ok": True,
        "pragma_version": __version__,
        "cwd": str(cwd),
        "manifest_exists": (cwd / "pragma.yaml").exists(),
        "lock_exists": (cwd / "pragma.lock.json").exists(),
        "pre_commit_config_exists": (cwd / ".pre-commit-config.yaml").exists(),
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
