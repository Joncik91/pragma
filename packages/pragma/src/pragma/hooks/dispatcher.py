from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from pragma.core.audit import append_audit
from pragma.hooks import post_tool_use, pre_tool_use, session_start, stop

_HANDLERS: dict[str, Callable[[dict[str, Any], Path], dict[str, Any]]] = {
    "session-start": session_start.handle,
    "pre-tool-use": pre_tool_use.handle,
    "post-tool-use": post_tool_use.handle,
    "stop": stop.handle,
}


def _safe_default(event: str) -> dict[str, Any]:
    if event in ("pre-tool-use", "post-tool-use"):
        return {"permissionDecision": "allow"}
    return {"continue": True}


def _write_json(stdout: IO[str], obj: dict[str, Any]) -> None:
    stdout.write(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _reject_unknown(stdout: IO[str], event: str) -> int:
    _write_json(
        stdout,
        {
            "error": "unknown_hook_event",
            "message": f"unknown event: {event!r}",
            "remediation": (
                f"Valid events: {sorted(_HANDLERS)}. Check .claude/settings.json hook command."
            ),
            "context": {"event": event},
        },
    )
    return 1


def _reject_missing_stdin(stdout: IO[str], event: str) -> int:
    _write_json(
        stdout,
        {
            "error": "hook_input_missing",
            "message": "No stdin received from Claude Code.",
            "remediation": ("This command is invoked by Claude Code hooks; don't run it directly."),
            "context": {"event": event},
        },
    )
    return 1


def dispatch(
    *,
    event: str,
    stdin: IO[str],
    stdout: IO[str],
    cwd: Path | None,
) -> int:
    if event not in _HANDLERS:
        return _reject_unknown(stdout, event)

    raw = stdin.read().strip()
    if not raw:
        return _reject_missing_stdin(stdout, event)

    try:
        event_input = json.loads(raw)
    except json.JSONDecodeError:
        _write_json(stdout, _safe_default(event))
        return 0

    effective_cwd = cwd or Path.cwd()
    try:
        result = _HANDLERS[event](event_input, effective_cwd)
    except Exception as exc:
        with contextlib.suppress(Exception):
            append_audit(
                effective_cwd / ".pragma",
                event="hook_crash",
                actor="cli",
                slice=None,
                from_state=None,
                to_state=None,
                reason=f"{type(exc).__name__}: {exc}",
                context={"hook": event},
            )
        _write_json(stdout, _safe_default(event))
        return 0

    _write_json(stdout, result)
    return 0
