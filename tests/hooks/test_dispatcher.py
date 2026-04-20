from __future__ import annotations

import io
import json

from pragma.hooks.dispatcher import dispatch


def test_dispatch_routes_session_start() -> None:
    inp = io.StringIO(json.dumps({"session_id": "x", "source": "startup"}))
    out = io.StringIO()
    exit_code = dispatch(event="session-start", stdin=inp, stdout=out, cwd=None)
    assert exit_code == 0
    result = json.loads(out.getvalue())
    assert "continue" in result or "additionalContext" in result


def test_dispatch_routes_pre_tool_use(hook_input_pre_tool_use: dict) -> None:
    inp = io.StringIO(json.dumps(hook_input_pre_tool_use))
    out = io.StringIO()
    exit_code = dispatch(event="pre-tool-use", stdin=inp, stdout=out, cwd=None)
    assert exit_code == 0
    result = json.loads(out.getvalue())
    assert "permissionDecision" in result


def test_dispatch_unknown_event() -> None:
    out = io.StringIO()
    exit_code = dispatch(
        event="nope",
        stdin=io.StringIO("{}"),
        stdout=out,
        cwd=None,
    )
    assert exit_code == 1
    assert json.loads(out.getvalue())["error"] == "unknown_hook_event"


def test_dispatch_missing_stdin() -> None:
    out = io.StringIO()
    exit_code = dispatch(
        event="session-start",
        stdin=io.StringIO(""),
        stdout=out,
        cwd=None,
    )
    assert exit_code == 1
    assert json.loads(out.getvalue())["error"] == "hook_input_missing"


def test_dispatch_never_crashes_on_handler_exception(monkeypatch) -> None:
    from pragma.hooks import session_start as ss_module

    def boom(event_input: dict, cwd) -> dict:
        raise RuntimeError("pragma bug")

    monkeypatch.setattr(ss_module, "handle", boom)
    out = io.StringIO()
    exit_code = dispatch(
        event="session-start",
        stdin=io.StringIO('{"session_id":"x","source":"startup"}'),
        stdout=out,
        cwd=None,
    )
    assert exit_code == 0
    result = json.loads(out.getvalue())
    assert result.get("continue") is True
