from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from pragma.core.audit import append_hook_crash
from pragma.hooks import post_tool_use, pre_tool_use, session_start, stop

# Module references, not bound .handle attributes, so tests can
# monkeypatch module.handle and dispatch will pick up the patched
# function at call time.
_HANDLER_MODULES = {
    "session-start": session_start,
    "pre-tool-use": pre_tool_use,
    "post-tool-use": post_tool_use,
    "stop": stop,
}


def _get_handler(event: str) -> Callable[[dict[str, Any], Path], dict[str, Any]]:
    return _HANDLER_MODULES[event].handle


def _safe_default(event: str, *, reason: str | None = None) -> dict[str, Any]:
    """Fail-safe response when a hook's own dispatch/parse path misfires.

    PreToolUse / PostToolUse fail open (permissionDecision: allow) so a
    crashed Pragma hook never DoSes an editing turn. SessionStart is
    advisory; {continue: true} lets the session proceed. Stop is the
    only event where a silent {continue: true} is wrong: the user
    would never know the gate check didn't run. For Stop we fail to
    {continue: false, stopReason: ...} so Claude Code ends the turn
    cleanly and the reason is surfaced in the UI.
    """
    if event in ("pre-tool-use", "post-tool-use"):
        return {"permissionDecision": "allow"}
    if event == "stop":
        return {
            "continue": False,
            "stopReason": reason or "pragma stop hook failed; turn ended without gate check",
        }
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
                f"Valid events: {sorted(_HANDLER_MODULES)}. "
                "Check .claude/settings.json hook command."
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
    if event not in _HANDLER_MODULES:
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
        result = _get_handler(event)(event_input, effective_cwd)
    except Exception as exc:
        # KI-6: route crash forensics to hook-crash.jsonl, not audit.jsonl.
        # Keeps the real gate-transition log clean of noise from hook
        # bugs / test runs that exercise crash paths.
        with contextlib.suppress(Exception):
            append_hook_crash(
                effective_cwd / ".pragma",
                event=f"hook_crash:{event}",
                reason=f"{type(exc).__name__}: {exc}",
            )
        _write_json(
            stdout,
            _safe_default(
                event, reason=f"pragma {event} hook crashed: {type(exc).__name__}: {exc}"
            ),
        )
        return 0

    _write_json(stdout, result)
    return 0
