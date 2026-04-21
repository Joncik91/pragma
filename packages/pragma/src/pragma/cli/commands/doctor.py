"""`pragma doctor` — self-diagnostic + recovery-advice report.

In v0.1 doctor was a stub that dumped six booleans. v1.0 lifts it into a
real recovery tool: it still dumps the original state fields (for
backwards compatibility), and ADDITIONALLY appends a ``diagnostics:``
list — one entry per detected failure mode — each with a ``remediation``
string the user (or Claude Code) can execute verbatim.

doctor always exits zero. Diagnostics are informational; the caller
decides what to do next.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma import __version__
from pragma.core.recovery import diagnose


@trace("REQ-001")
def doctor() -> None:
    """Print local install + project state as JSON, with recovery advice."""
    cwd = Path.cwd()
    diagnostics = diagnose(cwd)
    payload: dict[str, object] = {
        "ok": True,
        "pragma_version": __version__,
        "cwd": str(cwd),
        "manifest_exists": (cwd / "pragma.yaml").exists(),
        "lock_exists": (cwd / "pragma.lock.json").exists(),
        "pre_commit_config_exists": (cwd / ".pre-commit-config.yaml").exists(),
        "pragma_dir_exists": (cwd / ".pragma").exists(),
        "claude_settings_exists": (cwd / ".claude" / "settings.json").exists(),
        "diagnostics": diagnostics,
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
