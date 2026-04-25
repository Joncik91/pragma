"""Red tests for REQ-031 — narrative adr surfaces all missing options at once.

BUG-035. The Typer command had five `typer.Option(..., ...)` required
options; calling the command without them produced one error per
invocation. A user discovering the contract had to fail at least
five times. Fix: collect the missing fields and raise once.
"""

from __future__ import annotations

import json
import subprocess
import sys

from pragma_sdk import set_permutation, trace


def _invoke(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pragma", *args],
        capture_output=True,
        text=True,
    )


@trace("REQ-031")
def _assert_lists_all_missing_in_one_error() -> None:
    result = _invoke(["narrative", "adr", "test-slug"])
    assert result.returncode != 0, f"adr without args must fail; stdout={result.stdout!r}"
    # Spec §5.4: narrative commands write JSON errors to stderr.
    payload = json.loads(result.stderr.strip().splitlines()[-1])
    assert payload["error"] == "narrative_missing_args", (
        f"adr without args must use narrative_missing_args error code; got {payload!r}"
    )
    msg = payload["message"]
    for required in ("context", "decision", "consequences", "alternatives", "who"):
        assert required in msg.lower(), (
            f"error message must list every missing option; missing {required!r} in {msg!r}"
        )


@trace("REQ-031")
def _assert_full_args_succeed() -> None:
    result = _invoke(
        [
            "narrative",
            "adr",
            "test-slug",
            "--context",
            "ctx",
            "--decision",
            "dec",
            "--consequences",
            "cons",
            "--alternatives",
            "alt",
            "--who",
            "me",
        ],
    )
    assert result.returncode == 0, f"adr with all args must succeed; stdout={result.stdout!r}"
    assert "ctx" in result.stdout
    assert "dec" in result.stdout


def test_req_031_lists_all_missing_in_one_error() -> None:
    with set_permutation("lists_all_missing_in_one_error"):
        _assert_lists_all_missing_in_one_error()


def test_req_031_full_args_succeed() -> None:
    with set_permutation("full_args_succeed"):
        _assert_full_args_succeed()
